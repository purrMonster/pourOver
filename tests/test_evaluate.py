from pourover.evaluate import main

from .conftest import ROOT


def test_runner_on_sample_without_model(tmp_path, capsys):
    code = main(["--messages", str(ROOT / "eval/sample.yaml"), "--world", str(ROOT / "eval/world.yaml"), "--out", str(tmp_path)])
    out = capsys.readouterr().out
    assert "4 messages" in out and "exact 75%" in out and "wrong deletes 0" in out
    assert code == 1  # 75% < 90%: no go, as expected without a model
    assert (tmp_path / "no-model.json").exists()
