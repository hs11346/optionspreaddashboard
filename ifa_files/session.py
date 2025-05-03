import refinitiv.dataplatform as rdp

# Object used to open a RDP session

session = rdp.open_platform_session(
    "*",
    rdp.GrantPassword(
        username = 'u3594016@connect.hku.hk',
        password = '*'
    )
)
