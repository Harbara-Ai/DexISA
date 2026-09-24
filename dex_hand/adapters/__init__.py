def create_adapter(hand, **kwargs):
    # Keep the real-hardware modules importable without installing the optional
    # MuJoCo simulation runtime.
    backend=kwargs.pop('backend','mock' if hand in ('allegro_v5','robotiq_2f85') else 'mujoco')
    if backend=='mujoco' and hand in ('allegro_v5','robotiq_2f85'):
        from .official_mujoco import AllegroV5MuJoCoAdapter,Robotiq2F85MuJoCoAdapter
        return {'allegro_v5':AllegroV5MuJoCoAdapter,
                'robotiq_2f85':Robotiq2F85MuJoCoAdapter}[hand](**kwargs)
    if hand == 'allegro_v5':
        if backend!='mock':raise ValueError(f'unsupported backend: {backend}')
        from .allegro_v5 import AllegroV5Adapter
        return AllegroV5Adapter(**kwargs)
    if hand == 'robotiq_2f85':
        if backend!='mock':raise ValueError(f'unsupported backend: {backend}')
        from .robotiq_2f85 import Robotiq2F85Adapter
        return Robotiq2F85Adapter(**kwargs)
    if hand == 'wuji':
        if backend!='mujoco':raise ValueError(f'unsupported backend: {backend}')
        from .wuji_mujoco import WujiMuJoCoAdapter
        return WujiMuJoCoAdapter(**kwargs)
    if hand == 'sharpa':
        if backend!='mujoco':raise ValueError(f'unsupported backend: {backend}')
        from .sharpa_mujoco import SharpaMuJoCoAdapter
        return SharpaMuJoCoAdapter(**kwargs)
    raise ValueError(f'unknown embodiment: {hand}')
