"""shared.flow.export 数据导出单元测试。"""
import csv
import json

from shared.flow.export import export_rows


class TestExport:
    def test_csv_roundtrip(self, tmp_path):
        p = tmp_path / "out.csv"
        headers = ["名称", "数量"]
        rows = [["a,b", 1], ['引号"x"', 2]]
        out = export_rows(headers, rows, p)
        assert out and out.exists()
        with open(p, encoding="utf-8-sig", newline="") as f:
            data = list(csv.reader(f))
        assert data[0] == headers
        assert data[1] == ["a,b", "1"]
        assert data[2] == ['引号"x"', "2"]

    def test_json_roundtrip(self, tmp_path):
        p = tmp_path / "out.json"
        headers = ["name", "count"]
        rows = [["x", 3]]
        out = export_rows(headers, rows, p)
        assert out and out.exists()
        items = json.loads(p.read_text(encoding="utf-8"))
        assert items == [{"name": "x", "count": "3"}]

    def test_creates_parent_dirs(self, tmp_path):
        p = tmp_path / "sub" / "dir" / "out.csv"
        assert export_rows(["h"], [["v"]], p)
        assert p.exists()
