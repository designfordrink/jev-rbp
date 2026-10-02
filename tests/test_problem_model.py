from jev_rbp.problem import CommodityType, Demand, RBPInstance, Settings


def test_intermodal_is_a_first_class_commodity_type() -> None:
    demand = Demand(
        demand_id=1,
        origin_yard_id=10,
        dest_yard_id=20,
        volume=1000,
        commodity_type=CommodityType.INTERMODAL,
    )
    instance = RBPInstance(nodes={}, links={}, demands={1: demand}, settings=Settings())
    assert instance.demands[1].commodity_type is CommodityType.INTERMODAL


def test_default_settings_match_released_benchmark_defaults() -> None:
    settings = Settings()
    assert settings.min_block_vol_short == 350
    assert settings.min_block_vol_medium == 700
    assert settings.min_block_vol_long == 1050
    assert settings.max_circuitous_ratio == 1.3
    assert settings.demand_multiplier == 1.0
