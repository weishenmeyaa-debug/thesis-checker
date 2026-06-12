"""
报告生成模块
生成可下载的 HTML 格式检查报告
"""

import os
from checker import Severity


def generate_report(results, output_path):
    """生成 HTML 报告"""
    html = _build_html(results)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


def generate_report_html(results):
    """返回 HTML 字符串（用于页面直接展示）"""
    return _build_html(results)


def _build_html(results):
    total_errors = sum(r.summary.get("errors", 0) for r in results if hasattr(r, 'summary'))
    total_warnings = sum(r.summary.get("warnings", 0) for r in results if hasattr(r, 'summary'))
    total_infos = sum(r.summary.get("infos", 0) for r in results if hasattr(r, 'summary'))

    sections = []
    for result in results:
        sections.append(_build_document_section(result))

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>毕业设计格式检查报告</title>
<style>
{_get_css()}
</style>
</head>
<body>
<div class="report">
  <header>
    <h1>毕业设计格式检查报告</h1>
    <p class="meta">生成时间：{_import_datetime()}</p>
    <div class="summary-bar">
      <span class="badge error">错误 {total_errors}</span>
      <span class="badge warning">警告 {total_warnings}</span>
      <span class="badge info">提示 {total_infos}</span>
      <span class="badge count">共 {len(results)} 个文件</span>
    </div>
  </header>
  {"".join(sections)}
</div>
</body>
</html>"""


def _import_datetime():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _build_document_section(result):
    errors = [i for i in result.issues if i.severity == Severity.ERROR]
    warnings = [i for i in result.issues if i.severity == Severity.WARNING]
    infos = [i for i in result.issues if i.severity == Severity.INFO]

    error_rows = "".join(_build_issue_row(i) for i in errors)
    warning_rows = "".join(_build_issue_row(i) for i in warnings)
    info_rows = "".join(_build_issue_row(i) for i in infos)

    has_error = hasattr(result, 'error') and getattr(result, 'error', None)

    return f"""
  <section class="document">
    <h2>{result.filename}</h2>
    {"<p class='parse-error'>解析失败：" + str(getattr(result, 'error', '')) + "</p>" if has_error else ""}
    <div class="doc-summary">
      <span class="badge error">错误 {len(errors)}</span>
      <span class="badge warning">警告 {len(warnings)}</span>
      <span class="badge info">提示 {len(infos)}</span>
    </div>

    {_build_table("错误（必须修改）", error_rows) if errors else ""}
    {_build_table("警告（建议修改）", warning_rows) if warnings else ""}
    {_build_table("提示（仅供参考）", info_rows) if infos else ""}

    {"" if result.issues else "<p class='all-good'>未发现格式问题。</p>"}
  </section>"""


def _build_table(title, rows):
    return f"""
    <h3>{title}</h3>
    <table>
      <thead>
        <tr>
          <th width="12%">位置</th>
          <th width="8%">分类</th>
          <th width="22%">问题描述</th>
          <th width="15%">正确格式</th>
          <th width="15%">实际格式</th>
          <th width="28%">出错原文</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>"""


def _build_issue_row(issue):
    content = getattr(issue, 'content', '') or ''
    content_display = f'<span class="content-preview">{content}</span>' if content else '<span class="no-content">—</span>'
    return f"""
        <tr>
          <td>{issue.location}</td>
          <td><span class="tag">{issue.category}</span></td>
          <td>{issue.description}</td>
          <td class="expected">{issue.expected}</td>
          <td class="actual">{issue.actual}</td>
          <td class="content-cell">{content_display}</td>
        </tr>"""


def _get_css():
    return """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, "Microsoft YaHei", "微软雅黑", sans-serif; background: #f5f5f5; color: #333; line-height: 1.6; }
.report { max-width: 1100px; margin: 0 auto; padding: 20px; }
header { background: #fff; padding: 30px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
header h1 { font-size: 24px; margin-bottom: 8px; }
.meta { color: #888; font-size: 14px; margin-bottom: 15px; }
.summary-bar { display: flex; gap: 10px; flex-wrap: wrap; }
.badge { padding: 4px 12px; border-radius: 4px; font-size: 13px; font-weight: 500; }
.badge.error { background: #fee; color: #c33; }
.badge.warning { background: #fff8e1; color: #e6a700; }
.badge.info { background: #e3f2fd; color: #1565c0; }
.badge.count { background: #f0f0f0; color: #666; }
.document { background: #fff; padding: 25px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.document h2 { font-size: 18px; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 2px solid #eee; }
.document h3 { font-size: 15px; margin: 18px 0 10px; color: #555; }
.doc-summary { display: flex; gap: 10px; margin-bottom: 15px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 15px; }
thead { background: #fafafa; }
th { text-align: left; padding: 8px 10px; border-bottom: 2px solid #ddd; font-weight: 500; color: #666; }
td { padding: 8px 10px; border-bottom: 1px solid #eee; vertical-align: top; }
tr:hover { background: #f9f9f9; }
.expected { color: #2e7d32; }
.actual { color: #c62828; }
.tag { background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-size: 12px; }
.content-cell { font-size: 12px; color: #555; max-width: 0; overflow: hidden; }
.content-preview { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; word-break: break-all; line-height: 1.5; background: #fff8e1; padding: 3px 6px; border-radius: 3px; border-left: 3px solid #ffa726; }
.no-content { color: #ccc; }
.parse-error { color: #c33; background: #fee; padding: 10px; border-radius: 4px; margin: 10px 0; }
.all-good { color: #2e7d32; background: #e8f5e9; padding: 15px; border-radius: 4px; text-align: center; font-size: 15px; }
"""
