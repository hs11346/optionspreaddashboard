#!/usr/bin/env python
# coding: utf-8

# In[1]:
import pandas as pd
import json
import numpy as np
import matplotlib.pyplot as plt

# Matplotlib requires dates in float format for surface plots.
'''
Please try to change it to altair charts for streamlit integration
'''
def convert_yyyymmdd_to_float(date_string_array):
    import datetime
    import matplotlib.dates as dates
    
    date_float_array = []
    for date_string in date_string_array:
        if len(date_string)==10:
            date_float = dates.date2num(datetime.datetime.strptime(date_string, '%Y-%m-%d'))
        else:
            date_float = dates.date2num(datetime.datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%SZ'))
        date_float_array.append(date_float)
    return date_float_array


# In[1]:


# Convert float date back to Y-m-d for the Surface y axis tick labels
def format_date(x, pos=None):
    import matplotlib.dates as dates
        
    return dates.num2date(x).strftime('%Y-%m-%d') #use FuncFormatter to format dates


# In[1]:


def plot_surface(surfaces, surfaceTag,delta_plot=False):
    
    # This import registers the 3D projection, but is otherwise unused.
    from mpl_toolkits.mplot3d import Axes3D
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib import cm
    import matplotlib.ticker as ticker # import LinearLocator, FormatStrFormatter
 
    surfaces = pd.DataFrame(data=surfaces)
    surfaces.set_index('surfaceTag', inplace=True)
    surface = surfaces[surfaces.index == surfaceTag]['surface'][0]
    
    strike_axis = surface[0][1:]
    surface = surface[1:]
    time_axis = []
    surface_grid = []
    for line in surface:
        time_axis.append(line[0])
        surface_grid_line = line[1:]
        surface_grid.append(surface_grid_line)

    time_axis = convert_yyyymmdd_to_float(time_axis)
    
    if delta_plot:
        # When plotting FX Delta rather than Strike 
        # I'm converting the x axis value from Delta to Put Delta
        delta_axis = list(map(convert_delta, strike_axis))
        x = np.array(delta_axis, dtype=float)
    else:
        x = np.array(strike_axis, dtype=float)
        
    y = np.array(time_axis, dtype=float)
    Z = np.array(surface_grid, dtype=float)
    
    X,Y = np.meshgrid(x,y)
    
    fig = plt.figure(figsize=[9,6])
    
    ax = plt.axes(projection='3d')
    ax.set_facecolor('0.25')
    ax.set_xlabel('Delta' if delta_plot else 'Moneyness',color='y',labelpad=10)
    ax.set_ylabel('Expiry',color='y',labelpad=15)
    ax.set_zlabel('Volatilities',color='y')
    ax.tick_params(axis='both', colors='w')

    ax.yaxis.set_major_formatter(ticker.FuncFormatter(format_date))
    
    title = 'Vol Surface for : ' + str(surfaceTag)
    ax.set_title(title,color='w')
    
    surf = ax.plot_surface(X,Y,Z, cmap=cm.coolwarm, linewidth=0, antialiased=False)    
    return fig


# In[1]:


def convert_delta(delta):
    if (delta<0):
        return -delta
    elif (delta>0):
        return 1-delta
    else:
        return 0.5


# In[4]:


def plot_smile(surfaces, maturity, delta_plot=False):
    import pandas as pd
    import matplotlib.pyplot as plt
    import math

    #fig = plt.figure(figsize=[15,5])
    plt.rcParams["figure.figsize"] = (20,5)
    fig, ax = plt.subplots(facecolor='0.25')
    ax.set_facecolor('0.25')
    ax.tick_params(axis='both', colors='w')
    ax.set_xlabel('Delta' if delta_plot else 'Moneyness',color='y')
    ax.set_ylabel('Volatility',color='y')
    #fig.layout.update(xaxis_type = 'category')        
    
    surfaces = pd.DataFrame(data=surfaces)

    for i in range(0,surfaces.shape[0]):
        label = surfaces.loc[i,['surfaceTag']]['surfaceTag']
        surface = surfaces.loc[i,['surface']]['surface']
        error = surfaces.loc[i,['error']]['error'] if 'error' in surfaces else 0.0

        x=[]
        y=[]
        if (type(error) is float):
            x = surface[0][1:]
            y = surface[maturity][1:]
            title = 'Smile ' + str(surface[maturity][0])
            ax.set_title(title,color='w')
            # When plotting FX Delta rather than Strike 
            # I'm transforming the delta axis value delta call to make the chart easier to plot
            if delta_plot:
                delta_axis = list(map(convert_delta, x))
                ax.plot(delta_axis,y,label=label)
            else:    
                ax.plot(x,y,label=label)

    plt.legend()
    return fig
    


# In[7]:


def plot_term_volatility (surfaces, strike):
    import pandas as pd
    import matplotlib.pyplot as plt
    import math
    import itertools

    plt.rcParams["figure.figsize"] = (20,5)
    fig, ax = plt.subplots(facecolor='0.25')
    ax.set_facecolor('0.25')
    ax.tick_params(axis='both', colors='w')
    ax.set_xlabel('Time to expiry',color='y')
    ax.set_ylabel('Volatility',color='y')
    
    surfaces = pd.DataFrame(data=surfaces)

    for i in range(0,surfaces.shape[0]):
        error = surfaces.loc[i,['error']]['error'] if 'error' in surfaces else 0.0
        label = surfaces.loc[i,['surfaceTag']]['surfaceTag']
        x=[]
        y=[]
        if (type(error) is float):
            title = 'Term Structure ' + str("{:.0%}".format(float(surfaces.loc[i,['surface']]['surface'][0][strike])))
            surface = pd.DataFrame(surfaces.loc[i,['surface']]['surface'][1:])
            dtx = surface[0]
            # ETI and FX currently returning different datetime format
            # so strip time from FX
            x = dtx.str.slice(stop=10)
            y = surface[strike]
            ax.set_title(title,color='w')
            ax.set_facecolor('0.25')
            ax.plot(x,y,label=label)

    plt.legend()
    return fig
    


# In[6]:


def plot_forward_curve(surfaces, surfaceTag):
    
    # This import registers the 3D projection, but is otherwise unused.
    from mpl_toolkits.mplot3d import Axes3D
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib import cm
    from matplotlib.ticker import LinearLocator, FormatStrFormatter
 
    plt.rcParams["figure.figsize"] = (15,5)
    fig, ax = plt.subplots(facecolor='0.25')
    ax.set_facecolor('0.25')
    ax.set_xlabel('Time',color='y')
    ax.set_ylabel('Price',color='y')
    ax.set_title(surfaceTag,color='w')
    ax.tick_params(axis='both', colors='w')

    surfaces = pd.DataFrame(data=surfaces)
    surfaces.set_index('surfaceTag', inplace=True)
    fwd_curve = surfaces[surfaces.index == surfaceTag]['forwardCurve'][0]['dataPoints']
    
    x=[]
    y=[]
    for key in fwd_curve.keys():
        x.append(key)
        y.append(fwd_curve[key])

    ax.set_facecolor('0.25')
    ax.plot(x,y)


def smooth_line(x, y, nb_data_points, smoothing_factor=None):
    
    import scipy.interpolate as interpolate
    import numpy as np
    import math as math

    s = 0.0 if (smoothing_factor==0.0) else len(x) + (2 * smoothing_factor - 1) * math.sqrt(2*len(x))

    t,c,k = interpolate.splrep(x,y,k=3,s=s)
    
    xnew = np.linspace(x[0], x[-1], nb_data_points)
    spline =  interpolate.BSpline(t, c, k, extrapolate=False)
    
    xnew = np.linspace(x[0], x[-1], nb_data_points)
    ynew = spline(xnew)

    return xnew, ynew


# In[1]:


def convert_ISODate_to_float(date_string_array):
    import datetime
    import matplotlib.dates as dates
    
    date_float_array = []
    for date_string in date_string_array:
        date_float = dates.date2num(datetime.datetime.strptime(date_string, '%Y-%m-%d'))
        date_float_array.append(date_float)
    return date_float_array


# In[4]:


def plot_zc_curves(curves, curve_tenors=None, smoothingfactor=None):
    
    import pandas as pd
    import matplotlib.pyplot as plt

    tenors = curve_tenors if curve_tenors!=None else curves['description']['curveDefinition']['availableTenors'][:-1]
    s = smoothingfactor if smoothingfactor != None else 0.0

    plt.rcParams["figure.figsize"] = (20,5)
    fig, ax = plt.subplots(facecolor='0.25')
    ax.set_facecolor('0.25')
    ax.tick_params(axis='both', colors='w')

    ax.set_xlabel('Time')
    ax.set_ylabel('ZC Rate')
    ax.set_title(response.data.raw['data'][0]['curveDefinition']['name'],color='w')

    for tenor in tenors:
        curve = pd.DataFrame(data=curves['curves'][tenor]['curvePoints'])
        x = convert_ISODate_to_float(curve['endDate'])
        y = curve['ratePercent']
        xnew, ynew = smooth_line(x,y,100,s)
        ax.plot(xnew,ynew,label=tenor)

    plt.xticks(rotation='vertical')
    plt.legend(loc='upper left',fontsize='x-large')
    return fig


# In[ ]:




