import refinitiv.dataplatform as rdp

session = rdp.open_platform_session(
    "eb849581f17b4d9180e48d1cd10b2a8635ab1ffd",
    rdp.GrantPassword(
        username = 'u3594016@connect.hku.hk',
        password = 'hkutgQuants2023'
    )
)