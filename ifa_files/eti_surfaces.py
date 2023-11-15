import refinitiv.dataplatform as rdp
from ifa_files.session import *
import streamlit as st

'''
Function to get surface object from RDP session, which is passed to main.py to plot using plotting_helper.py functions
'''
def surface_template(ric):
    template = {
                "surfaceTag": ric,
                "underlyingType": "Eti",
                "underlyingDefinition": {
                    "instrumentCode": ric
                },
                "surfaceParameters": {
                    "inputVolatilityType": "settle",
                    "volatilityModel": "SSVI",
                    "xAxis": "Date",
                    "yAxis": "Moneyness"
                },
                "surfaceLayout": {
                    "format": "Matrix",
                }
            }
    return template

@st.cache_data()
def get_surface():
    rics = ['SPY']
    eti_request_body = {
        "universe": [surface_template(ric) for ric in rics],
        "outputs": ["ForwardCurve"]
    }
    vs_endpoint = rdp.Endpoint(session, "https://api.refinitiv.com/data/quantitative-analytics-curves-and-surfaces/v1/surfaces")
    eti_response = vs_endpoint.send_request(
        method = rdp.Endpoint.RequestMethod.POST,
        body_parameters = eti_request_body
    )
    surfaces = eti_response.data.raw['data']
    return surfaces