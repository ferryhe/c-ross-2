from __future__ import annotations

import json
import sys
from pathlib import Path


AI_AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AI_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AI_AGENT_DIR))

from scripts import build_ready_data as ready_data_module


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_build_ready_data_outputs_expected_artifacts(tmp_path):
    source = tmp_path / "Knowledge_Base_MarkDown"
    rules_dir = source / "rules"
    attachments_dir = source / "attachments"
    rules_dir.mkdir(parents=True)
    attachments_dir.mkdir(parents=True)

    (attachments_dir / "附件4：压力测试情景.md").write_text(
        "---\n"
        "title: 附件4：压力测试情景\n"
        "category: attachments\n"
        "source_type: .pdf\n"
        "---\n\n"
        "# 附件4：压力测试情景\n\n"
        "列出压力测试情景。\n",
        encoding="utf-8",
    )

    (rules_dir / "保险公司偿付能力监管规则第2号：最低资本.md").write_text(
        "---\n"
        "title: 保险公司偿付能力监管规则第2号：最低资本\n"
        "category: rules\n"
        "source_type: .pdf\n"
        "---\n\n"
        "# 保险公司偿付能力监管规则第2号：最低资本\n\n"
        "## 第一章 总则\n\n"
        "第一条 最低资本由三部分组成，并可参考附件4。 \n\n"
        "## 第三章 计量方法\n\n"
        "第十五条 计算公式如下：\n\n"
        "$$\n"
        "\\mathrm{MC}^{*}=\\sqrt{\\mathrm{MC}^2+\\mathrm{LA}^2}\n"
        "$$\n\n"
        "| 项目 | 数值 |\n"
        "| --- | --- |\n"
        "| 系数 | 0.35 |\n",
        encoding="utf-8",
    )

    output_root = source / "ready_data"
    stats = ready_data_module.build_ready_data(source=source, output_root=output_root, section_max_tokens=200)

    assert stats["doc_count"] == 2
    assert (output_root / "doc_catalog.jsonl").exists()
    assert (output_root / "title_aliases.jsonl").exists()
    assert (output_root / "doc_summaries.jsonl").exists()
    assert (output_root / "sections_structured.jsonl").exists()
    assert (output_root / "formula_cards.jsonl").exists()
    assert (output_root / "relations_graph.json").exists()
    assert (output_root / "ready_data_manifest.json").exists()
    manifest = json.loads((output_root / "ready_data_manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_root"] == "Knowledge_Base_MarkDown"


def test_build_ready_data_generates_rule_aliases_and_formula_cards(tmp_path):
    source = tmp_path / "Knowledge_Base_MarkDown"
    rules_dir = source / "rules"
    rules_dir.mkdir(parents=True)

    (rules_dir / "保险公司偿付能力监管规则第2号：最低资本.md").write_text(
        "---\n"
        "title: 保险公司偿付能力监管规则第2号：最低资本\n"
        "category: rules\n"
        "---\n\n"
        "# 保险公司偿付能力监管规则第2号：最低资本\n\n"
        "第十五条 计算公式如下：\n\n"
        "$$\n"
        "\\mathrm{MC}^{*}=\\sqrt{\\mathrm{MC}^2+\\mathrm{LA}^2}\n"
        "$$\n",
        encoding="utf-8",
    )

    output_root = source / "ready_data"
    ready_data_module.build_ready_data(source=source, output_root=output_root, section_max_tokens=200)

    aliases = _read_jsonl(output_root / "title_aliases.jsonl")
    formulas = _read_jsonl(output_root / "formula_cards.jsonl")

    assert any(item["alias"] == "规则第2号" for item in aliases)
    assert formulas
    assert formulas[0]["doc_id"] == "rules/保险公司偿付能力监管规则第2号：最低资本.md"
    assert "MC" in "".join(formulas[0]["variables"])


def test_build_ready_data_generates_relation_edges(tmp_path):
    source = tmp_path / "Knowledge_Base_MarkDown"
    rules_dir = source / "rules"
    attachments_dir = source / "attachments"
    rules_dir.mkdir(parents=True)
    attachments_dir.mkdir(parents=True)

    (attachments_dir / "附件4：压力测试情景.md").write_text(
        "# 附件4：压力测试情景\n\n内容。\n",
        encoding="utf-8",
    )
    (rules_dir / "保险公司偿付能力监管规则第2号：最低资本.md").write_text(
        "# 保险公司偿付能力监管规则第2号：最低资本\n\n"
        "第一条 具体要求见附件4。\n",
        encoding="utf-8",
    )

    output_root = source / "ready_data"
    ready_data_module.build_ready_data(source=source, output_root=output_root, section_max_tokens=200)

    graph = json.loads((output_root / "relations_graph.json").read_text(encoding="utf-8"))
    assert any(edge["relation"] == "mentions_attachment" for edge in graph["edges"])


def test_build_ready_data_preserves_empty_front_matter_values_and_related_docs(tmp_path):
    source = tmp_path / "Knowledge_Base_MarkDown"
    rules_dir = source / "rules"
    attachments_dir = source / "attachments"
    rules_dir.mkdir(parents=True)
    attachments_dir.mkdir(parents=True)

    (attachments_dir / "附件4：压力测试情景.md").write_text(
        "---\n"
        "title: 附件4：压力测试情景\n"
        "category: attachments\n"
        "source_type: .pdf\n"
        "publish_date: \n"
        "converted_engine: mistral\n"
        "---\n\n"
        "# 附件4：压力测试情景\n\n"
        "压力测试情景正文。\n",
        encoding="utf-8",
    )

    (rules_dir / "保险公司偿付能力监管规则第2号：最低资本.md").write_text(
        "---\n"
        "title: 保险公司偿付能力监管规则第2号：最低资本\n"
        "category: rules\n"
        "source_type: .pdf\n"
        "publish_date: \n"
        "converted_engine: mistral\n"
        "---\n\n"
        "# 保险公司偿付能力监管规则第2号：最低资本\n\n"
        "附件4\n\n"
        "最低资本由三部分组成，并应参考附件4。\n",
        encoding="utf-8",
    )

    output_root = source / "ready_data"
    ready_data_module.build_ready_data(source=source, output_root=output_root, section_max_tokens=200)

    catalog = _read_jsonl(output_root / "doc_catalog.jsonl")
    summaries = _read_jsonl(output_root / "doc_summaries.jsonl")

    rule_catalog = next(item for item in catalog if item["category"] == "rules")
    rule_summary = next(item for item in summaries if item["category"] == "rules")
    attachment_summary = next(item for item in summaries if item["category"] == "attachments")

    assert rule_catalog["publish_date"] == ""
    assert rule_catalog["source_type"] == ".pdf"
    assert rule_catalog["summary_short"].startswith("最低资本由三部分组成")
    assert rule_summary["related_doc_ids"] == ["attachments/附件4：压力测试情景.md"]
    assert attachment_summary["related_doc_ids"] == []


def test_build_ready_data_skips_summary_noise_for_notice_documents(tmp_path):
    source = tmp_path / "Knowledge_Base_MarkDown"
    notices_dir = source / "notices"
    notices_dir.mkdir(parents=True)

    (notices_dir / "关于优化保险公司偿付能力监管标准的通知.md").write_text(
        "---\n"
        "title: 国家金融监督管理总局关于优化保险公司偿付能力监管标准的通知\n"
        "category: notices\n"
        "---\n\n"
        "![image 1](image1.png)\n\n"
        "![image 2](image2.png)\n\n"
        "# 国家金融监督管理总局关于优化保险公司偿付能力监管标准的通知\n\n"
        "金规〔2023〕5号\n\n"
        "各金融监管局、各保险集团（控股）公司、保险公司、保险资产管理公司：\n\n"
        "为完善保险公司偿付能力监管标准，促进保险公司回归本源和稳健运行，现就有关事项通知如下：\n\n"
        "一、差异化调节最低资本要求。\n",
        encoding="utf-8",
    )

    output_root = source / "ready_data"
    ready_data_module.build_ready_data(source=source, output_root=output_root, section_max_tokens=200)

    catalog = _read_jsonl(output_root / "doc_catalog.jsonl")
    summaries = _read_jsonl(output_root / "doc_summaries.jsonl")

    notice_catalog = next(item for item in catalog if item["category"] == "notices")
    notice_summary = next(item for item in summaries if item["category"] == "notices")

    assert notice_catalog["summary_short"].startswith("为完善保险公司偿付能力监管标准")
    assert "金规〔2023〕5号" not in notice_catalog["summary_short"]
    assert notice_summary["summary_short"].startswith("为完善保险公司偿付能力监管标准")
