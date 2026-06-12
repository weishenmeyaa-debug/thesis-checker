"""
毕业设计格式检测工具 - Flask 主应用
支持上传规范文件和学生论文，生成可下载报告
"""

import os
import uuid
import json
import subprocess
import shutil
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, flash, jsonify
from checker import check_document, Severity
from spec_parser import parse_spec_docx, rules_to_json
from report import generate_report

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config["SHOW_FOOTER"] = True

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
REPORT_DIR = os.path.join(BASE_DIR, "reports")
SPEC_DIR = os.path.join(BASE_DIR, "specs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)
os.makedirs(SPEC_DIR, exist_ok=True)


@app.context_processor
def inject_footer():
    return dict(show_footer=app.config.get("SHOW_FOOTER", False))


def convert_doc_to_docx(doc_path):
    """用 macOS textutil 将 .doc 转为 .docx"""
    docx_path = doc_path.rsplit(".", 1)[0] + ".docx"
    try:
        subprocess.run(
            ["textutil", "-convert", "docx", doc_path, "-output", docx_path],
            check=True, capture_output=True, timeout=30
        )
        return docx_path
    except Exception as e:
        return None


def get_spec_rules():
    """获取当前使用的规范规则 JSON 路径"""
    # 优先使用用户上传的最新规范
    specs = sorted([f for f in os.listdir(SPEC_DIR) if f.endswith(".json")], reverse=True)
    if specs:
        return os.path.join(SPEC_DIR, specs[0])
    # 回退到内置规则
    default = os.path.join(BASE_DIR, "format_rules.json")
    if os.path.exists(default):
        return default
    return None


@app.route("/")
def index():
    specs = sorted([f for f in os.listdir(SPEC_DIR) if f.endswith("_rules.json")], reverse=True)
    default_spec = os.path.join(BASE_DIR, "format_rules.json")
    has_builtin = os.path.exists(default_spec)
    return render_template("index.html", specs=specs, has_builtin=has_builtin)


@app.route("/examples")
def examples():
    # 加载当前规范规则，传给模板动态渲染示例
    rules_json_path = get_spec_rules()
    rules_dict = {}
    if rules_json_path:
        try:
            with open(rules_json_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for r in raw:
                section = r.get("section", "")
                rules_dict[section] = r
        except Exception:
            pass

    # 提取常用参数，给模板用
    def rule_val(section, key, default=""):
        return rules_dict.get(section, {}).get(key, default)

    params = {
        "body_font": rule_val("body_text", "font", "宋体"),
        "body_size": rule_val("body_text", "size_pt", 12),
        "body_size_name": rule_val("body_text", "size_name", "小四"),
        "caption_font": rule_val("figure_caption", "font", "宋体"),
        "caption_size": rule_val("figure_caption", "size_pt", 10.5),
        "caption_size_name": rule_val("figure_caption", "size_name", "五号"),
        "footnote_font": rule_val("footnote", "font", "宋体"),
        "footnote_size": rule_val("footnote", "size_pt", 9),
        "footnote_size_name": rule_val("footnote", "size_name", "小五"),
        "ref_entry_font": rule_val("reference_entry", "font", "宋体"),
        "ref_entry_size": rule_val("reference_entry", "size_pt", 10.5),
        "ref_entry_size_name": rule_val("reference_entry", "size_name", "五号"),
        "line_spacing": rule_val("line_spacing_body", "line_spacing_pt", 22),
        "ref_spacing": rule_val("reference_entry", "line_spacing_pt", 18),
        "ref_min": rule_val("reference_count", "min_count", 20),
        "ref_foreign_min": rule_val("reference_foreign_count", "min_count", 3),
        "fig_notes": rule_val("figure_caption", "notes", ""),
        "fn_notes": rule_val("footnote", "notes", ""),
        "title1_font": rule_val("level1_title", "font", "宋体"),
        "title1_size": rule_val("level1_title", "size_pt", 15),
        "title1_size_name": rule_val("level1_title", "size_name", "小三"),
        "title2_font": rule_val("level2_title", "font", "宋体"),
        "title2_size": rule_val("level2_title", "size_pt", 14),
        "title2_size_name": rule_val("level2_title", "size_name", "四号"),
        "abstract_body_font": rule_val("abstract_zh_body", "font", "楷体"),
        "abstract_body_size": rule_val("abstract_zh_body", "size_pt", 12),
    }

    return render_template("examples.html", **params)


@app.route("/editor")
def editor():
    specs = sorted([f for f in os.listdir(SPEC_DIR) if f.endswith("_rules.json")], reverse=True)
    default_spec = os.path.join(BASE_DIR, "format_rules.json")
    has_builtin = os.path.exists(default_spec)
    return render_template("editor.html", specs=specs, has_builtin=has_builtin)


@app.route("/editor/active")
def editor_active():
    """返回当前生效的规则及来源信息"""
    rules_path = get_spec_rules()
    if not rules_path:
        return jsonify(ok=True, source="none", source_label="无规则文件", rules=[])

    try:
        with open(rules_path, "r", encoding="utf-8") as f:
            rules = json.load(f)
    except Exception as e:
        return jsonify(ok=False, error=str(e))

    builtin_path = os.path.join(BASE_DIR, "format_rules.json")
    if os.path.abspath(rules_path) == os.path.abspath(builtin_path):
        source = "builtin"
        source_label = "内置规则"
    else:
        source = os.path.basename(rules_path)
        source_label = source.replace("_rules.json", "").replace("_", " ")

    return jsonify(ok=True, source=source, source_label=source_label, rules=rules)


@app.route("/editor/save", methods=["POST"])
def editor_save():
    """保存编辑后的规则为新规范文件"""
    data = request.get_json()
    if not data or not data.get("name") or not data.get("rules"):
        return jsonify(ok=False, error="缺少名称或规则数据")

    rules = data["rules"]
    errors = []
    for i, r in enumerate(rules):
        if not r.get("section", "").strip():
            errors.append(f"第{i+1}条：section 不能为空")
        if not r.get("label", "").strip():
            errors.append(f"第{i+1}条：label 不能为空")
        if r.get("size_pt") is not None and r["size_pt"] != "":
            try:
                v = float(r["size_pt"])
                if v <= 0 or v > 100:
                    errors.append(f"第{i+1}条：字号 {v} 不合理")
            except (ValueError, TypeError):
                errors.append(f"第{i+1}条：字号格式错误")
        if r.get("line_spacing_pt") is not None and r["line_spacing_pt"] != "":
            try:
                v = float(r["line_spacing_pt"])
                if v <= 0 or v > 100:
                    errors.append(f"第{i+1}条：行距 {v} 不合理")
            except (ValueError, TypeError):
                errors.append(f"第{i+1}条：行距格式错误")
    if errors:
        return jsonify(ok=False, error="；".join(errors))

    safe_name = data["name"].replace(" ", "_").replace("/", "_")
    filename = f"{safe_name}_rules.json"
    filepath = os.path.join(SPEC_DIR, filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(ok=False, error=str(e))


@app.route("/editor/load/<spec_name>")
def editor_load(spec_name):
    """加载已有规范文件，返回 JSON"""
    if spec_name == "__builtin__":
        filepath = os.path.join(BASE_DIR, "format_rules.json")
    else:
        filepath = os.path.join(SPEC_DIR, spec_name)

    if not os.path.exists(filepath):
        return jsonify(ok=False, error="规范文件不存在")

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            rules = json.load(f)
        return jsonify(ok=True, rules=rules)
    except Exception as e:
        return jsonify(ok=False, error=str(e))


@app.route("/editor/delete/<spec_name>", methods=["POST"])
def editor_delete(spec_name):
    """删除已有规范"""
    path = os.path.join(SPEC_DIR, spec_name)
    if os.path.exists(path):
        os.remove(path)
    return jsonify(ok=True)


@app.route("/upload_spec", methods=["POST"])
def upload_spec():
    """上传规范文件，解析并保存规则"""
    spec_file = request.files.get("spec_file")
    if not spec_file or spec_file.filename == "":
        flash("请选择规范文件", "error")
        return redirect(url_for("index"))

    filename = spec_file.filename
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in ("doc", "docx"):
        flash("规范文件仅支持 .doc 或 .docx 格式", "error")
        return redirect(url_for("index"))

    # 保存文件
    task_id = uuid.uuid4().hex[:8]
    safe_name = filename.replace(" ", "_")
    filepath = os.path.join(SPEC_DIR, f"{task_id}_{safe_name}")
    spec_file.save(filepath)

    # 如果是 .doc，先转换
    docx_path = filepath
    if ext == "doc":
        docx_path = convert_doc_to_docx(filepath)
        if not docx_path:
            flash("无法转换 .doc 文件，请另存为 .docx 后重试", "error")
            return redirect(url_for("index"))

    # 解析规范
    try:
        rules = parse_spec_docx(docx_path)
        rules_json_path = os.path.join(SPEC_DIR, f"{task_id}_rules.json")
        rules_to_json(rules, rules_json_path)
        flash(f"规范文件解析成功，提取 {len(rules)} 条规则", "success")
    except Exception as e:
        flash(f"规范文件解析失败: {e}", "error")
        return redirect(url_for("index"))

    return redirect(url_for("index"))


@app.route("/delete_spec/<spec_name>", methods=["POST"])
def delete_spec(spec_name):
    """删除已上传的规范"""
    path = os.path.join(SPEC_DIR, spec_name)
    if os.path.exists(path):
        os.remove(path)
    return redirect(url_for("index"))


@app.route("/check", methods=["POST"])
def check():
    files = request.files.getlist("files")
    if not files or all(f.filename == "" for f in files):
        flash("请上传至少一个 Word 文件", "error")
        return redirect(url_for("index"))

    # 获取规范规则
    rules_json_path = get_spec_rules()

    results = []
    for f in files:
        filename = f.filename
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ("doc", "docx"):
            continue

        # 保存上传文件
        task_id = uuid.uuid4().hex[:8]
        filepath = os.path.join(UPLOAD_DIR, f"{task_id}_{filename}")
        f.save(filepath)

        # .doc 需要转换
        docx_path = filepath
        if ext == "doc":
            docx_path = convert_doc_to_docx(filepath)
            if not docx_path:
                results.append(type("Err", (), {
                    "filename": filename,
                    "issues": [],
                    "summary": {"errors": 0, "warnings": 0, "infos": 0},
                    "error": "无法转换 .doc 文件，请另存为 .docx 后重试"
                })())
                continue

        # 检测
        try:
            result = check_document(docx_path, rules_json_path=rules_json_path)
            results.append(result)
        except Exception as e:
            error_msg = str(e)
            if "Package not found" in error_msg or "not a zip file" in error_msg:
                error_msg = "文件格式损坏，请确认文件未损坏且为有效的 Word 文档"
            elif "encrypted" in error_msg.lower() or "password" in error_msg.lower():
                error_msg = "文件已加密或设置了密码，请先解密后再上传"
            elif "PermissionError" in error_msg:
                error_msg = "文件被占用，请关闭 Word 后重试"
            else:
                error_msg = f"文件解析失败，请确认为有效的 Word 文档（.doc 或 .docx）"
            results.append(type("Err", (), {
                "filename": filename,
                "issues": [],
                "summary": {"errors": 0, "warnings": 0, "infos": 0},
                "error": error_msg
            })())

        # 清理本次上传的文件
        for cleanup_path in [filepath, docx_path]:
            if cleanup_path and os.path.exists(cleanup_path):
                try:
                    os.remove(cleanup_path)
                except OSError:
                    pass

    if not results:
        flash("没有有效的 Word 文件（.doc 或 .docx）", "error")
        return redirect(url_for("index"))

    # 生成报告
    report_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(REPORT_DIR, f"report_{report_id}.html")
    generate_report(results, report_path)

    return render_template("report.html", results=results, report_id=report_id)


@app.route("/download/<report_id>")
def download_report(report_id):
    report_path = os.path.join(REPORT_DIR, f"report_{report_id}.html")
    if os.path.exists(report_path):
        return send_file(report_path, as_attachment=True,
                         download_name=f"格式检查报告_{report_id}.html")
    return "报告不存在", 404


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5001)
    args = parser.parse_args()
    app.run(debug=True, port=args.port)
