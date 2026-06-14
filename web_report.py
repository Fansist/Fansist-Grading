"""web_report.py

Public web page behind each slab's QR code. Scanning the QR opens
``/card/<cert_id>``, which renders the full TAG-style grade report (overall on
1-10 and 1-1000 scales, the four sub-grades, per-corner and per-edge breakdowns,
centering measurements, surface defect density) plus the annotated card images.

Run a local instance:

    pip install -r requirements.txt
    FANSIST_STORE=./cards python web_report.py      # serves http://localhost:8000

Reports are read from a filesystem store written by ``report.save_report``
(one folder per cert id). ``create_app(store_dir)`` is a factory so it's easy to
test and to point at any store / mount behind a real domain.
"""

from __future__ import annotations

import os

from flask import Flask, abort, render_template_string, send_from_directory

from report import load_report

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ r.cert_id }} — Fansist Grade Report</title>
<style>
  :root{--bg:#0f1115;--card:#1a1d24;--ink:#e8eaed;--mut:#9aa0aa;--acc:#4da3ff;}
  *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);
    font:15px/1.5 system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
  .wrap{max-width:920px;margin:0 auto;padding:24px}
  .top{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}
  .brand{font-weight:700;letter-spacing:.5px} .cert{color:var(--mut);font-size:13px}
  .hero{display:flex;gap:24px;align-items:center;background:var(--card);
    border-radius:16px;padding:24px;margin:16px 0}
  .big{font-size:64px;font-weight:800;line-height:1} .big small{font-size:20px;color:var(--mut)}
  .k1000{font-size:18px;color:var(--acc);font-weight:700}
  .grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
  @media(max-width:680px){.grid{grid-template-columns:repeat(2,1fr)}}
  .sub{background:var(--card);border-radius:12px;padding:14px;text-align:center}
  .sub .v{font-size:30px;font-weight:800} .sub .l{color:var(--mut);font-size:12px}
  .sub .n{color:var(--mut);font-size:11px;margin-top:2px}
  h2{font-size:14px;text-transform:uppercase;letter-spacing:1px;color:var(--mut);
    margin:26px 0 10px}
  table{width:100%;border-collapse:collapse;background:var(--card);border-radius:12px;overflow:hidden}
  td,th{padding:10px 12px;text-align:left;border-bottom:1px solid #262a33;font-size:14px}
  th{color:var(--mut);font-weight:600} tr:last-child td{border-bottom:none}
  .imgs{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
  @media(max-width:680px){.imgs{grid-template-columns:1fr}}
  .imgs figure{margin:0;background:var(--card);border-radius:12px;padding:8px}
  .imgs img{width:100%;border-radius:8px;display:block}
  .imgs figcaption{color:var(--mut);font-size:12px;text-align:center;padding:6px 0}
  .qr{display:flex;gap:16px;align-items:center;background:var(--card);
    border-radius:12px;padding:16px;margin-top:18px}
  .qr img{width:120px;height:120px;background:#fff;border-radius:8px;padding:6px}
  .disc{color:var(--mut);font-size:12px;margin-top:20px}
  a{color:var(--acc)}
</style></head><body><div class="wrap">

  <div class="top">
    <div class="brand">🃏 FANSIST <span style="color:var(--mut)">GRADING</span></div>
    <div class="cert">Cert {{ r.cert_id }} · graded {{ r.graded_at }}</div>
  </div>

  <div class="hero">
    <div>
      <div class="big">{{ fmt(r.overall_grade) }}<small>/10</small></div>
      {% if r.overall_score_1000 is not none %}
      <div class="k1000">{{ r.overall_score_1000 }} / 1000</div>{% endif %}
    </div>
    <div style="color:var(--mut)">
      Overall grade combined from the four sub-grades below.
      {% if r.meta.get('population_graded') %}<br>Population graded:
      {{ r.meta['population_graded'] }}.{% endif %}
    </div>
  </div>

  <div class="grid">
    <div class="sub"><div class="v">{{ fmt(r.centering_grade) }}</div>
      <div class="l">Centering</div><div class="n">{{ r.centering_label }}</div></div>
    <div class="sub"><div class="v">{{ fmt(r.corners_grade) }}</div>
      <div class="l">Corners</div><div class="n">{{ r.corners_label }}</div></div>
    <div class="sub"><div class="v">{{ fmt(r.edges_grade) }}</div>
      <div class="l">Edges</div><div class="n">{{ r.edges_label }}</div></div>
    <div class="sub"><div class="v">{{ fmt(r.surface_grade) }}</div>
      <div class="l">Surface</div><div class="n">{{ r.surface_label }}</div></div>
  </div>

  <h2>Centering</h2>
  <table>
    <tr><th>Horizontal (L : R)</th><td>{{ pc(r.centering_detail.horizontal_pct.left) }}
      / {{ pc(r.centering_detail.horizontal_pct.right) }}</td>
      <th>Vertical (T : B)</th><td>{{ pc(r.centering_detail.vertical_pct.top) }}
      / {{ pc(r.centering_detail.vertical_pct.bottom) }}</td></tr>
    <tr><th>Margins (px)</th><td colspan="3">
      L {{ r.centering_detail.margins_px.left }} ·
      R {{ r.centering_detail.margins_px.right }} ·
      T {{ r.centering_detail.margins_px.top }} ·
      B {{ r.centering_detail.margins_px.bottom }}</td></tr>
  </table>

  {% if r.corners_detail %}
  <h2>Corners (per corner)</h2>
  <table><tr>{% for k,v in r.corners_detail.items() %}
    <th>{{ k.replace('_',' ').title() }}</th>{% endfor %}</tr>
    <tr>{% for k,v in r.corners_detail.items() %}<td>{{ fmt(v) }}</td>{% endfor %}</tr></table>
  {% endif %}

  {% if r.edges_detail %}
  <h2>Edges (per edge)</h2>
  <table><tr>{% for k,v in r.edges_detail.items() %}
    <th>{{ k.title() }}</th>{% endfor %}</tr>
    <tr>{% for k,v in r.edges_detail.items() %}<td>{{ fmt(v) }}</td>{% endfor %}</tr></table>
  {% endif %}

  {% if r.surface_detail %}
  <h2>Surface</h2>
  <table><tr><th>Defect density</th>
    <td>{{ r.surface_detail.defect_density_pct }}%</td></tr></table>
  {% endif %}

  <h2>Imagery</h2>
  <div class="imgs">
    <figure><img src="{{ url('original') }}" alt="card"><figcaption>Detected card</figcaption></figure>
    <figure><img src="{{ url('centering') }}" alt="centering"><figcaption>Centering</figcaption></figure>
    <figure><img src="{{ url('condition') }}" alt="condition"><figcaption>Corners / edges / surface</figcaption></figure>
  </div>

  <div class="qr">
    <img src="{{ url('qr') }}" alt="QR">
    <div><div>Scan to reopen this report.</div>
      <div class="cert">{{ r.report_url }}</div></div>
  </div>

  <p class="disc">Automated estimate from computer-vision analysis of a single
  image — for reference, not an official third-party grade.</p>
</div></body></html>"""


def create_app(store_dir: str) -> Flask:
    """Create the Flask app serving reports from ``store_dir``."""
    app = Flask(__name__)
    store = os.path.abspath(store_dir)

    def fmt(v):
        return "—" if v is None else f"{v:g}"

    def pc(v):
        return f"{v:.0f}"

    @app.route("/card/<cert_id>")
    def card(cert_id):
        report = load_report(store, cert_id)
        if report is None:
            abort(404)
        return render_template_string(
            PAGE, r=report, fmt=fmt, pc=pc,
            url=lambda role: f"/card/{cert_id}/img/{report.images.get(role, '')}",
        )

    @app.route("/card/<cert_id>/img/<path:name>")
    def card_img(cert_id, name):
        cert_dir = os.path.join(store, cert_id)
        if not os.path.isdir(cert_dir):
            abort(404)
        return send_from_directory(cert_dir, name)

    @app.route("/health")
    def health():
        return {"ok": True, "store": store}

    @app.route("/")
    def index():
        return ("Fansist Grading — scan a slab's QR code, or open "
                "/card/&lt;cert_id&gt;.")

    return app


if __name__ == "__main__":
    store = os.environ.get("FANSIST_STORE", "./cards")
    os.makedirs(store, exist_ok=True)
    create_app(store).run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
