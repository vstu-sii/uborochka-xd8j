import webbrowser
from pathlib import Path
from tracer import read_traces

OUTPUT = Path("ml/tracing/dashboard.html")


def render_html(traces: list) -> str:
    rows = []
    for t in traces[::-1]:  # новые сверху
        status_color = "#2ecc71" if t["status"] == "success" else "#e74c3c"
        prompt_preview = str(t.get("prompt", ""))[:300]
        answer_preview = str(t.get("answer", ""))[:300]
        rows.append(f"""
        <tr>
          <td>{t['timestamp'][:19]}</td>
          <td>{t['model']}</td>
          <td style="color:{status_color};font-weight:bold">{t['status']}</td>
          <td>{t['latency_ms']} мс</td>
          <td>{t.get('tokens_out') or '—'}</td>
          <td><pre class="box">{prompt_preview}</pre></td>
          <td><pre class="box">{answer_preview}</pre></td>
        </tr>""")

    return f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><title>LLM Traces Dashboard</title>
<style>
body{{font-family:Arial;padding:20px;background:#f5f6fa}}
h1{{color:#2c3e50}}
table{{width:100%;border-collapse:collapse;background:#fff;box-shadow:0 2px 8px rgba(0,0,0,.08)}}
th,td{{padding:10px;border-bottom:1px solid #eee;text-align:left;vertical-align:top;font-size:13px}}
th{{background:#2c3e50;color:#fff}}
.box{{background:#f8f9fa;padding:8px;border-radius:4px;max-height:120px;overflow:auto;white-space:pre-wrap;font-size:11px}}
</style></head>
<body>
<h1>Трассировка LLM-вызовов</h1>
<p>Всего записей: <b>{len(traces)}</b>. Файл: <code>ml/tracing/traces.jsonl</code></p>
<table>
<tr><th>Время</th><th>Модель</th><th>Статус</th><th>Latency</th><th>Токены out</th><th>Промпт</th><th>Ответ</th></tr>
{''.join(rows)}
</table>
</body></html>"""


if __name__ == "__main__":
    traces = read_traces()
    OUTPUT.write_text(render_html(traces), encoding="utf-8")
    print(f"Дашборд сохранён: {OUTPUT.resolve()}")
    webbrowser.open(OUTPUT.resolve().as_uri())