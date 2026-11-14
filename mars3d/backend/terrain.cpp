// terrain.cpp — NAM C++ backend number cruncher
// Heavy geospatial compute that is painful in pure Python: per-cell slope /
// aspect / roughness / hazard from a MOLA heightmap, A* least-cost routing,
// and a NASA-style landing-site scorer. Exposed via a plain C ABI (extern "C")
// so the Python middle-end loads it with ctypes — no pybind, no ABI headaches.
//
// Build:  g++ -O3 -fPIC -shared terrain.cpp -o libterrain.so
//
// Grid convention (mirrors the app):
//   w x H grid, row 0 = +90 lat, row H-1 = -90 lat, col 0 = 0 lon E (wraps).
//   heights are int16 METRES relative to the MOLA areoid (PNG uint16 - 16384).

#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <vector>
#include <queue>
#include <limits>

extern "C" {

// ---------------------------------------------------------------------------
// terrain_compute: per-cell slope (deg), aspect (deg, 0=N clockwise),
// roughness (m, RMS of detrended residual in a (2r+1)^2 window), and a
// composite hazard index (0 safe .. 1 dangerous). Out arrays length w*H, f32.
//   m_per_px : horizontal metres per grid cell (equatorial ~14820 for 4 ppd)
//   rad      : neighbourhood radius in cells for roughness/hazard (e.g. 4)
// Slope: Horn 3x3 finite-difference (standard GIS method).
//   dz/dx = ((z_{r-1,c-1}+2z_{r,c-1}+z_{r+1,c-1}) - (z_{r-1,c+1}+2z_{r,c+1}+z_{r+1,c+1})) / (8*dx)
//   dz/dy = ((z_{r-1,c-1}+2z_{r-1,c}+z_{r-1,c+1}) - (z_{r+1,c-1}+2z_{r+1,c}+z_{r+1,c+1})) / (8*dy)
// Longitude wraps; poles use nearest row.
// ---------------------------------------------------------------------------
void terrain_compute(const int16_t* z, int w, int H,
                     double m_per_px, int rad,
                     float* slope, float* aspect, float* rough, float* hazard)
{
    const double dx = m_per_px, dy = m_per_px;
    const double RAD = 180.0/M_PI;
    for(int y=0;y<H;y++){
        int yu = (y>0)?y-1:y;
        int yd = (y<H-1)?y+1:y;
        for(int x=0;x<w;x++){
            int xl = (x>0)?x-1:w-1;
            int xr = (x<w-1)?x+1:0;
            long i = (long)y*w + x;
            double a = z[yu*w+xl], b = z[yu*w+x], c = z[yu*w+xr];
            double d = z[y *w+xl],             f = z[y *w+xr];
            double g = z[yd*w+xl], h = z[yd*w+x], k = z[yd*w+xr];
            double dzdx = ((a + 2*d + g) - (c + 2*f + k)) / (8.0*dx);
            double dzdy = ((a + 2*b + c) - (g + 2*h + k)) / (8.0*dy);
            double slp = atan(sqrt(dzdx*dzdx + dzdy*dzdy)) * RAD;
            slope[i] = (float)slp;
            double asp = atan2(dzdx, -dzdy) * RAD; if(asp<0) asp+=360.0;
            aspect[i] = (float)asp;

            // roughness: RMS residual after removing local mean, in (2r+1)^2 window
            double sum=0; int n=0;
            for(int yy=-rad; yy<=rad; yy++){
                int ny=y+yy; if(ny<0)ny=0; if(ny>=H)ny=H-1;
                for(int xx=-rad; xx<=rad; xx++){
                    int nx=x+xx; if(nx<0)nx+=w; if(nx>=w)nx-=w;
                    sum += z[ny*w+nx]; n++;
                }
            }
            double mean = sum/n;
            double ss=0;
            for(int yy=-rad; yy<=rad; yy++){
                int ny=y+yy; if(ny<0)ny=0; if(ny>=H)ny=H-1;
                for(int xx=-rad; xx<=rad; xx++){
                    int nx=x+xx; if(nx<0)nx+=w; if(nx>=w)nx-=w;
                    double dv = z[ny*w+nx]-mean; ss += dv*dv;
                }
            }
            double rms = sqrt(ss/n);
            rough[i] = (float)rms;
            // hazard composite: steep + rough => dangerous. Tuned so a <5deg, <50m
            // RMS plain scores ~0.02 and a 25deg / 300m scarp scores ~0.9.
            double sF = slp/30.0; if(sF>1)sF=1;
            double rF = rms/400.0; if(rF>1)rF=1;
            hazard[i] = (float)(0.6*sF + 0.4*rF);
        }
    }
}

// ---------------------------------------------------------------------------
// A* least-cost routing on the height grid (8-connected, longitude wraps).
// cost = step_dist * (1 + slope^2/6^2 * ws + rough/300 * wr + hazard*wh)
//        / returns the path packed into out_xy as [x0,y0,x1,y1,...].
// Returns path point count (0 if none). max_nodes caps memory.
// ---------------------------------------------------------------------------
int astar_path(const int16_t* z, int w, int H,
               const float* slope, const float* rough, const float* hazard,
               int sx, int sy, int gx, int gy,
               double ws, double wr, double wh,
               int* out_xy, int max_nodes)
{
    if(sx<0||sx>=w||sy<0||sy>=H||gx<0||gx>=w||gy<0||gy>=H) return 0;
    const long N=(long)w*H;
    std::vector<float> gscore(N, std::numeric_limits<float>::infinity());
    std::vector<int>  came(N, -1);
    std::vector<bool> closed(N, false);
    auto idx=[&](int x,int y){ return (long)y*w + x; };
    struct Node{ float f; long i; };
    auto cmp=[](const Node&a,const Node&b){ return a.f>b.f; };
    std::priority_queue<Node,std::vector<Node>,decltype(cmp)> open(cmp);

    long start=idx(sx,sy), goal=idx(gx,gy);
    // euclidean heuristic in cells (admissible since step>=1 cell)
    auto heur=[&](int x,int y){ double dx=x-gx, dy=y-gy; return (float)sqrt(dx*dx+dy*dy); };
    gscore[start]=0;
    open.push({heur(sx,sy), start});
    const int dx8[8]={1,1,0,-1,-1,-1,0,1};
    const int dy8[8]={0,1,1,1,0,-1,-1,-1};
    long popped=0;
    while(!open.empty()){
        Node cur=open.top(); open.pop();
        if(cur.i==goal) break;
        if(closed[cur.i]) continue;
        closed[cur.i]=true;
        if(++popped > 2000000) break;     // safety cap
        int cx=cur.i%w, cy=cur.i/w;
        for(int k=0;k<8;k++){
            int nx=cx+dx8[k]; if(nx<0)nx+=w; if(nx>=w)nx-=w;
            int ny=cy+dy8[k]; if(ny<0||ny>=H) continue;
            long ni=idx(nx,ny);
            if(closed[ni]) continue;
            double step = (k%2==0)?1.0:1.41421356;
            double s = slope[ni], r = rough[ni], hz = hazard[ni];
            double cost = step*(1.0 + (s*s/36.0)*ws + (r/300.0)*wr + hz*wh);
            double tentative = gscore[cur.i] + cost;
            if(tentative < gscore[ni]){
                gscore[ni]=(float)tentative;
                came[ni]=cur.i;
                open.push({(float)(tentative + heur(nx,ny)), ni});
            }
        }
    }
    if(came[goal]<0 && goal!=start) return 0;
    // reconstruct
    std::vector<long> rev;
    for(long c=goal; c>=0; c=came[c]){ rev.push_back(c); if(c==start) break; }
    int n=(int)rev.size(); if(n>max_nodes) n=max_nodes;
    for(int i=0;i<n;i++){ long c=rev[n-1-i]; out_xy[2*i]=c%w; out_xy[2*i+1]=c/w; }
    return n;
}

// ---------------------------------------------------------------------------
// landing_score: NASA-style landing-site suitability over a disc of `rad`
// cells around (cx,cy). Returns a 0..100 score (higher=better) and fills
// slope_mean (deg), rough_rms (m), elev_var (m^2), n_cells.
// Criteria mirror MSL/Perseverance landing ellipse preferences: low regional
// slope, low RMS roughness, low elevation variance (flat, predictable).
// ---------------------------------------------------------------------------
double landing_score(const int16_t* z, const float* slope, const float* rough,
                     int w, int H, int cx, int cy, int rad,
                     double* slope_mean, double* rough_rms, double* elev_var, int* n_cells)
{
    double sl=0, ro=0; double esum=0, essum=0; int n=0;
    for(int dy=-rad; dy<=rad; dy++){
        int ny=cy+dy; if(ny<0||ny>=H) continue;
        for(int dx=-rad; dx<=rad; dx++){
            if(dx*dx+dy*dy > rad*rad) continue;
            int nx=cx+dx; if(nx<0)nx+=w; if(nx>=w)nx-=w;
            long i=(long)ny*w+nx;
            sl += slope[i]; ro += rough[i];
            double e = z[i];
            esum += e; essum += e*e; n++;
        }
    }
    if(n==0){ *n_cells=0; return 0; }
    double sm=sl/n, rm=ro/n;
    double emu=esum/n, evar=essum/n - emu*emu; if(evar<0)evar=0;
    *slope_mean=sm; *rough_rms=rm; *elev_var=evar; *n_cells=n;
    // score: penalize slope (>15deg bad), roughness (>250m bad), elev variance (>4e5 bad)
    double sP = (sm<2)?1.0 : std::max(0.0, 1.0-(sm-2)/15.0);
    double rP = (rm<50)?1.0 : std::max(0.0, 1.0-(rm-50)/250.0);
    double vP = (evar<1e4)?1.0 : std::max(0.0, 1.0-(evar-1e4)/4e5);
    double score = 100.0*(0.45*sP + 0.35*rP + 0.20*vP);
    if(score<0)score=0; if(score>100)score=100;
    return score;
}

// ---------------------------------------------------------------------------
// version string (lets the Python side confirm it loaded the right build)
// ---------------------------------------------------------------------------
const char* terrain_version(){ return "nam-terrain-1.0 g++-O3"; }

}  // extern "C"
