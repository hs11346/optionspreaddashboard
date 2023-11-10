from vectorised_load_data import *
import matplotlib.pyplot as plt
from matplotlib import cm
import numpy as np
import altair as alt

def vol_surface(sym, CPFlag):
    df = cboe_opx_chain(sym)
    df = df[['dte','IV', 'strike']][df.CPFlag == CPFlag]
    df = df[(df.dte >= 10) & (df.dte <= 90)  ]
    df = df.set_index(['dte','strike']).unstack('strike')
    df.columns = df.columns.droplevel()
    df.replace(0, np.nan, inplace=True)
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    X, Y = np.meshgrid(df.columns.astype(int), df.index)
    ax.set_xlabel('Strike')
    ax.set_ylabel('DTE')
    ax.set_zlabel('Implied Volatility')
    ax.plot_surface(X, Y, df.to_numpy(), cmap=cm.gist_rainbow)

def vol_struc(sym, CPFlag):
    df = cboe_opx_chain(sym)
    df = df[['dte','IV', 'strike']][df.CPFlag == CPFlag]
    df = df[(df.dte >= 10) & (df.dte <= 90)  ]

    c = alt.Chart(df).mark_line().encode(
        x='Date',
        y='Close'
    )
    c.encoding.y.scale = alt.Scale(domain=[df.Close.min() * 0.95, df.Close.max() * 1.05])
    line = alt.Chart(pd.DataFrame({'Close': selection.strike_short.to_list()})).mark_rule().encode(y='Close',
                                                                                                   color=alt.value(
                                                                                                       "#FF0000"))



