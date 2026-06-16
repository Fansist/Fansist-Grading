"""grader_portal.py

Internal web portal for the HUMAN grader. Lists the queue of submitted cards,
shows each submission's high-quality images (with capture-quality flags), and
lets the grader enter a grade — which generates the customer's report (cert + QR
+ public page via web_report). No AI; the human decides the grade.

    FANSIST_STORE=./submissions python grader_portal.py     # http://localhost:8001

Point this and the public ``web_report`` at the SAME store (a graded submission
becomes servable at the public ``/card/<id>``).
"""

from __future__ import annotations

import os

from flask import Flask, abort, redirect, render_template_string, request, send_from_directory

from submission import (
    GRADE_FIELDS,
    STATUS_PENDING,
    grade_submission,
    list_submissions,
    load_submission,
)

_STYLE = """body{margin:0;background:#0f1115;color:#e8eaed;font:15px/1.5 system-ui,
  Segoe UI,Roboto,Helvetica,Arial,sans-serif}.wrap{max-width:900px;margin:0 auto;padding:24px}
  a{color:#4da3ff;text-decoration:none}h1{font-size:20px}
  table{width:100%;border-collapse:collapse;background:#1a1d24;border-radius:12px;overflow:hidden}
  td,th{padding:10px 12px;text-align:left;border-bottom:1px solid #262a33;font-size:14px}th{color:#9aa0aa}
  .imgs{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.imgs img{width:100%;border-radius:8px}
  .bad{color:#fc8181}.ok{color:#68d391}
  input,textarea{background:#0f1115;color:#e8eaed;border:1px solid #333;border-radius:8px;padding:8px;font:inherit}
  label{display:inline-block;min-width:90px;color:#9aa0aa}.row{margin:8px 0}
  button{background:#4da3ff;color:#0b1020;border:0;border-radius:8px;padding:10px 18px;font-weight:700;cursor:pointer}
  .pill{padding:2px 8px;border-radius:999px;font-size:12px;background:#262a33}"""

QUEUE = """<!doctype html><meta charset="utf-8"><title>Grader queue</title>
<style>%s</style><div class="wrap">
<h1>🃏 Grader queue <span class="pill">{{ rows|length }} pending</span></h1>
{%% if rows %%}<table><tr><th>Submitted</th><th>Card</th><th>QC</th><th>Id</th></tr>
{%% for r in rows %%}<tr>
  <td>{{ r.created_at }}</td><td>{{ r.name or '—' }}</td>
  <td>{%% if r.qc_ok %%}<span class="ok">pass</span>{%% elif r.qc_ok == False %%}<span class="bad">flagged</span>{%% else %%}—{%% endif %%}</td>
  <td><a href="/submission/{{ r.id }}">{{ r.id }}</a></td></tr>{%% endfor %%}</table>
{%% else %%}<p>Queue empty. New submissions appear here.</p>{%% endif %%}
<p style="margin-top:16px;color:#9aa0aa"><a href="/all">view all submissions</a></p>
</div>""" % _STYLE

DETAIL = """<!doctype html><meta charset="utf-8"><title>Grade {{ s.id }}</title>
<style>%s</style><div class="wrap">
<p><a href="/">&larr; queue</a></p>
<h1>{{ s.meta.get('name','Card') }} <span class="pill">{{ s.status }}</span></h1>
<div class="imgs">
{%% for role, fname in s.images.items() %%}
  <figure><img src="/submission/{{ s.id }}/img/{{ fname }}">
  <figcaption>{{ role }}
    {%% set q = s.qc.get(role) %%}
    {%% if q %%}{%% if q.ok %%}<span class="ok">QC pass</span>{%% else %%}<span class="bad">{{ q.issues|join('; ') }}</span>{%% endif %%}{%% endif %%}
  </figcaption></figure>
{%% endfor %%}
</div>
{%% if s.status == 'graded' %%}
  <p>Graded <b>{{ s.grade.overall }}</b> by {{ s.graded_by }}. Public report:
  <a href="/card/{{ s.id }}">/card/{{ s.id }}</a> (served by the report app).</p>
{%% else %%}
<h2>Enter grade</h2>
<form method="post" action="/submission/{{ s.id }}/grade">
  {%% for f in fields %%}<div class="row"><label>{{ f }}{%% if f=='overall' %%}*{%% endif %%}</label>
    <input name="{{ f }}" type="number" step="0.5" min="1" max="10"></div>{%% endfor %%}
  <div class="row"><label>grader</label><input name="graded_by" value="grader"></div>
  <div class="row"><label>notes</label><textarea name="notes" rows="2" cols="40"></textarea></div>
  <div class="row"><button type="submit">Submit grade</button></div>
</form>
{%% endif %%}
</div>""" % _STYLE


def create_app(store_dir: str) -> Flask:
    app = Flask(__name__)
    store = os.path.abspath(store_dir)

    @app.route("/")
    def queue():
        return render_template_string(QUEUE, rows=list_submissions(store, STATUS_PENDING))

    @app.route("/all")
    def all_subs():
        return render_template_string(QUEUE, rows=list_submissions(store))

    @app.route("/submission/<sid>")
    def detail(sid):
        sub = load_submission(store, sid)
        if sub is None:
            abort(404)
        return render_template_string(DETAIL, s=sub, fields=GRADE_FIELDS)

    @app.route("/submission/<sid>/grade", methods=["POST"])
    def grade(sid):
        if load_submission(store, sid) is None:
            abort(404)
        grades = {f: request.form.get(f) for f in GRADE_FIELDS}
        try:
            grade_submission(store, sid, grades,
                             graded_by=request.form.get("graded_by", "grader"),
                             notes=request.form.get("notes", ""))
        except ValueError as exc:
            return f"Error: {exc}", 400
        return redirect(f"/submission/{sid}")

    @app.route("/submission/<sid>/img/<path:name>")
    def img(sid, name):
        folder = os.path.join(store, sid)
        if not os.path.isdir(folder):
            abort(404)
        return send_from_directory(folder, name)

    @app.route("/health")
    def health():
        return {"ok": True, "store": store}

    return app


if __name__ == "__main__":
    store = os.environ.get("FANSIST_STORE", "./submissions")
    os.makedirs(store, exist_ok=True)
    create_app(store).run(host="0.0.0.0", port=int(os.environ.get("PORT", "8001")))
