import xarray as xr
import numpy as np
import pandas as pd
import os
import matplotlib.pyplot as plt
import cartopy.crs as ccrs

from pyfloods import weather_type
from pyfloods import paths,region
from pyfloods.region import wtype as wtrgn
from pyfloods.anomalies import streamfunction,rainfall
from pyfloods.region import lower_py_river as lpr
import pyfloods.visualize as viz

map_proj = ccrs.Orthographic(-60, -10)
data_proj = ccrs.PlateCarree()

pars = {
    'n_clusters': 6,
    'wt_prop': 0.95,
    'nsim': 100,
    'pcscaling': 1
}

recalculate = False
try:
    cluster_ts = xr.open_dataarray(paths.file_weather_types)
    data_pars = {
        'n_clusters': cluster_ts.attrs.get('n_clusters'),
        'wt_prop': cluster_ts.attrs.get('wt_prop'),
        'nsim': cluster_ts.attrs.get('nsim'),
        'pcscaling': cluster_ts.attrs.get('pcscaling')
    }
    if (data_pars == pars):
        print(cluster_ts.attrs.get('classifiability'))
    else:
        os.remove(paths.file_weather_types)
        recalculate=True
except:
    recalculate = True

if recalculate:
    psi = streamfunction.get_data()
    psi = psi.sel(lon = slice(wtrgn.lonmin, wtrgn.lonmax),
                  lat = slice(wtrgn.latmin, wtrgn.latmax))
    psi = psi.sel(time = np.in1d(psi['time.month'], [11, 12, 1, 2]))
    psi = psi.sel(time = slice('1979-11-01', '2016-02-29'))
    np.random.seed(22591)
    best_centroid, cluster_ts, classifiability = weather_type.XrEofCluster(
        ds=psi['anomaly'],
        n_clusters=pars.get('n_clusters'),
        prop=pars.get('wt_prop'),
        nsim=pars.get('nsim'),
        pcscaling=pars.get('pcscaling'),
        verbose = True
    )
    print("Classifiability Index: {}".format(classifiability))
    cluster_ts.attrs.update(pars)
    cluster_ts.attrs.update({'classifiability': classifiability})
    cluster_ts.to_netcdf(paths.file_weather_types, format='NETCDF4')

wt = cluster_ts.to_dataframe(name='wtype')
wt['wtype'] = np.int_(wt['wtype'])
wt_counts = wt.groupby('wtype').size()
wt_counts2 = wt['2015-11-01':'2016-02-29'].groupby('wtype').size()
wt_prop = pd.DataFrame({'climatology': wt_counts / np.sum(wt_counts),
              'NDJF1516': wt_counts2 / np.sum(wt_counts2)})
print(wt_prop)

# Plot Proportion of Days
plt.figure(figsize=(8.5, 4.5))
plt.plot(wt_prop['climatology'], label = "Climatology")
plt.plot(wt_prop['NDJF1516'], label = "2015-16")
plt.xlabel("Weather Type")
plt.ylabel("Proportion of Total Days")
plt.legend()
plt.grid()
plt.savefig(os.path.join(paths.figures, 'wt_occurrence_fraction.pdf'), bbox_inches='tight')


# Plot Anomalies
wt_all = np.unique(wt['wtype'])
psi = streamfunction.get_data()
prcp = rainfall.get_data()

fig, axes = viz.SetupAxes(ncol = wt_all.size, nax = 2 * wt_all.size, proj = map_proj, figsize = [18, 5])
for i,w in enumerate(wt_all):
    def selector(ds):
        times = wt.loc[wt['wtype'] == w].index
        ds = ds.sel(time = np.in1d(ds.time, times))
        ds = ds.mean(dim = 'time')
        return(ds)

    # Row 1: 850 hPa wind
    ax = axes[0, i]
    ax.set_title('WT {}: {:.1%} of days'.format(w, wt_prop['climatology'].values[i]))
    C0 = selector(psi['anomaly']).plot.contourf(
        transform = ccrs.PlateCarree(), ax=ax,
        cmap = 'PuOr', extend="both",
        levels=np.linspace(-4.5e4, 4.5e4, 10),
        add_colorbar=False, add_labels=False
    )
    ax.add_patch(region.wtype.as_patch(color='black'))
    #
    ax = axes[1, i]
    C1 = selector(prcp['anomaly']).plot.contourf(
        transform = ccrs.PlateCarree(), ax=ax,
        cmap = 'BrBG', extend="both",
        levels=np.linspace(-6, 6, 13),
        add_colorbar=False, add_labels=False
    )
    ax.add_patch(region.wtype.as_patch(color='black'))

plt.tight_layout()
fig.subplots_adjust(right=0.94)
cax0 = fig.add_axes([0.97, 0.55, 0.0075, 0.35])
cax2 = fig.add_axes([0.97, 0.05, 0.0075, 0.4])
cbar0 = fig.colorbar(C0, cax = cax0)
cbar0.formatter.set_powerlimits((4, 4))
cbar0.update_ticks()
cbar0.set_label(r'$\psi_{850}$ Anomaly [$m^2$/s]', rotation=270)
cbar0.ax.get_yaxis().labelpad = 20
cbar1 = fig.colorbar(C1, cax=cax2)
cbar1.set_label('Precip. Anomaly [mm/d]', rotation=270)
cbar1.ax.get_yaxis().labelpad = 20

viz.FormatAxes(axes[0,:], extent = region.southern_hemisphere.as_extent())
viz.FormatAxes(axes[1,:], extent = region.south_america.as_extent())

fig.savefig(os.path.join(paths.figures, 'weather-type-composite.pdf'), bbox_inches='tight')


# Plot WT Time Series
prcp_rpy = prcp['raw'].sel(lon = slice(lpr.lonmin, lpr.lonmax),
                    lat = slice(lpr.latmin, lpr.latmax)).mean(
            dim=['lon', 'lat']).to_dataframe(name='raw')
wt_prcp = prcp_rpy.join(wt['wtype']).dropna()
wt_prcp = wt_prcp['2015-11-01':'2016-02-29']

time = wt_prcp.index
rain = wt_prcp.raw.values
wt_vec = np.int_(wt_prcp.wtype.values)

colors = plt.get_cmap('Accent', 6).colors

plt.style.use('ggplot')
fig,ax = plt.subplots(nrows=1, ncols=1, figsize=(14,4))
wt_prcp.raw.plot(ax=ax)
ax.axhline(prcp_rpy.raw.quantile(0.50), label="p50", color='blue', linestyle='--', linewidth=0.75)
ax.axhline(prcp_rpy.raw.quantile(0.90), label="p90", color='blue', linestyle='--', linewidth=0.75)
ax.axhline(prcp_rpy.raw.quantile(0.99), label="p99", color='blue', linestyle='--', linewidth=0.75)
ax.set_ylabel('Area-Averaged Rainfall [mm/d]')
ax.grid(True)
for i,t in enumerate(time):
    ax.text(t, rain[i], '{:d}'.format(wt_vec[i]), color=colors[wt_vec[i]-1], size=12, weight='bold')
fig.savefig(os.path.join(paths.figures, 'wt-rain-time-series.pdf'), bbox_inches='tight')
