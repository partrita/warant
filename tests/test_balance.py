"""Unit tests for balance configuration loading, fallback, and live overrides."""

import json
import tempfile

from warant import gamedata as g


def test_balance_config_loaded():
    """Verify that gamedata loads configurations properly."""
    assert "worker" in g.UNITS
    assert "acid_ant" in g.UNITS
    assert "granary" in g.BUILDINGS
    assert "pheromone" in g.RESEARCH or "foraging" in g.RESEARCH
    assert g.UNITS["worker"].attack == 5
    assert g.BUILDINGS["granary"].base_food == 80.0


def test_balance_config_override():
    """Verify that updating balance config and reloading modifies gamedata values."""
    with open(g.BALANCE_CONFIG_FILE, encoding="utf-8") as f:
        data = json.load(f)
    
    orig_attack = data["units"]["worker"]["attack"]
    try:
        data["units"]["worker"]["attack"] = 999
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            temp_path = f.name
        
        g.reload_balance(temp_path)
        assert g.UNITS["worker"].attack == 999
    finally:
        # Restore default
        g.reload_balance()
        assert g.UNITS["worker"].attack == orig_attack


def test_test_mode_speed_reduction():
    """Verify that test mode speeds up time by 1000x."""
    orig_mode = g.is_test_mode()
    try:
        g.set_test_mode(False)
        normal_b_time = g.building_time("fungus_farm", 1)
        normal_u_time = g.unit_build_time("worker", 1)
        normal_r_time = g.research_time("foraging", 1, 1)

        g.set_test_mode(True)
        fast_b_time = g.building_time("fungus_farm", 1)
        fast_u_time = g.unit_build_time("worker", 1)
        fast_r_time = g.research_time("foraging", 1, 1)

        assert abs(fast_b_time - normal_b_time / 1000.0) < 1e-5
        assert abs(fast_u_time - normal_u_time / 1000.0) < 1e-5
        assert abs(fast_r_time - normal_r_time / 1000.0) < 1e-5
    finally:
        g.set_test_mode(orig_mode)
