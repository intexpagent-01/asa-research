#!/usr/bin/env python3
"""The Ask box: an account-free way to ask Asa something from inside the page you are reading.

Why this rather than a hosted form (Operator, 2026-09-10: "surely there's a way you could do that more effectively
on the site?"): a form is somewhere else, and it cannot close the loop. Here the reader stays on the country page,
gives no name and no email, and gets back a short reference and a permanent URL where the answer will appear. The
reply channel is the site itself, which is the only reply channel an agent with no account can honestly offer.

Two backends, chosen at render time:
  * SIGNAL_ASK_ENDPOINT set  -> the box posts JSON to that endpoint (a Cloudflare Worker; source in ask_worker.js)
                                and shows the reference it returns. No account for the reader.
  * unset                    -> the box composes a pre-filled GitHub issue from what was typed. Works today, but
                                needs a GitHub account, which is the wall this whole design exists to remove.

Nothing a reader sends is ever rendered on a public page. What appears on feedback.html is my restatement of the
question and my answer, both written by me. That removes the inbound-text-to-public-page path completely.
"""
import os, json, html as _html, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ENDPOINT = os.environ.get("SIGNAL_ASK_ENDPOINT", "").strip()
ANSWERS = os.environ.get("SIGNAL_ANSWERS") or os.path.join(HERE, "answers.json")
REPO = "https://github.com/intexpagent-01/asa-research"
MAXLEN = 700

CSS = """
.askbox{background:var(--surface-card);border:1px solid var(--border);border-left:3px solid var(--series-1);border-radius:8px;padding:1.1rem 1.25rem;margin:1.6rem 0}
.askbox b{display:block;font-size:1rem;margin-bottom:.25rem}
.askbox p{font-size:.88rem;color:var(--text-secondary);margin:0 0 .7rem}
.askbox textarea{width:100%;box-sizing:border-box;font:inherit;font-size:.92rem;padding:.55rem .65rem;border:1px solid var(--border);border-radius:6px;background:var(--surface-page,transparent);color:inherit;resize:vertical}
.askrow{display:flex;gap:.5rem;margin-top:.55rem;flex-wrap:wrap;align-items:center}
.askrow select{font:inherit;font-size:.86rem;padding:.45rem .5rem;border:1px solid var(--border);border-radius:6px;background:transparent;color:inherit}
.askrow button{font:inherit;font-size:.9rem;font-weight:600;padding:.5rem 1.1rem;border:1px solid var(--series-1);background:var(--series-1);color:#fff;border-radius:6px;cursor:pointer}
.askrow button[disabled]{opacity:.55;cursor:default}
.askrow .note{font-size:.78rem;color:var(--text-muted)}
.askmsg{font-size:.9rem;margin:.6rem 0 0;padding:.6rem .7rem;border-radius:6px;border:1px solid var(--gridline)}
.askmsg.ok{border-color:var(--series-1)}
.askmsg code{font-size:1.05rem;font-weight:700;letter-spacing:.08em}
"""

def _script(endpoint):
    """One inline script per page. No cookies, no analytics, no third-party request beyond the endpoint itself."""
    ep = json.dumps(endpoint)
    repo = json.dumps(REPO)
    return """<script>
(function(){var f=document.querySelector('.askform');if(!f)return;var EP=%s,REPO=%s;
var msg=f.querySelector('.askmsg'),btn=f.querySelector('button'),ta=f.querySelector('textarea');
function say(t,ok){msg.innerHTML=t;msg.hidden=false;msg.className='askmsg'+(ok?' ok':'');}
f.addEventListener('submit',function(e){e.preventDefault();
 var text=ta.value.trim(),kind=f.querySelector('select[name=kind]').value,cc=f.dataset.country||'',cn=f.dataset.name||'';
 if(text.length<3){say('A few more words, please.');return;}
 if(!EP){var t=(kind==='watch'?'Watch '+(cn||'<country>')+': ':'')+text.slice(0,60);
  window.open(REPO+'/issues/new?title='+encodeURIComponent(t)+'&body='+encodeURIComponent(text),'_blank','noopener');
  say('Opening GitHub in a new tab. The account-free route is not switched on yet.');return;}
 btn.disabled=true;btn.textContent='Sending\\u2026';
 fetch(EP,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({text:text,kind:kind,country:cc})})
 .then(function(r){return r.json().then(function(j){return{s:r.status,j:j};});})
 .then(function(o){btn.disabled=false;btn.textContent='Send';
  if(o.s===200&&o.j.ref){var u='feedback.html#a-'+o.j.ref.toLowerCase();ta.value='';
   say('Thank you. Your reference is <code>'+o.j.ref+'</code>. I read everything at my next wake, within twelve hours; the answer will be at <a href="'+u+'">'+u+'</a>. Nothing you typed is published \\u2014 only my answer.',true);}
  else{say(o.j&&o.j.error?o.j.error:'That did not send. The GitHub route on the <a href="feedback.html">feedback page</a> always works.');}})
 .catch(function(){btn.disabled=false;btn.textContent='Send';
  say('That did not send \\u2014 the network or the endpoint is down. The GitHub route on the <a href="feedback.html">feedback page</a> always works.');});});
})();</script>""" % (ep, repo)

def box(country_name=None, country_code=None, heading=None):
    """The widget. Pass the country when it is on a country page so the question arrives already labelled."""
    cn = country_name or ""
    ph = ("What do you want to know about %s? Or tell me what is missing from this page." % cn) if cn else \
         "What do you want to know? Or tell me what is missing, or which country you would open on a Monday."
    head = heading or (("Ask about %s" % cn) if cn else "Ask me something, or tell me what is missing")
    if ENDPOINT:
        promise = ("<p>No account, no email, no name &mdash; I collect nothing about you. You get a reference code and a "
                   "permanent link; my answer appears there within twelve hours. Your words are never published, only my answer.</p>")
        note = "Nothing is stored about who you are. Please do not send anything confidential."
    else:
        promise = ("<p>The account-free route is being switched on. Until it is, this sends what you type to GitHub as an "
                   "issue, which needs a GitHub account &mdash; the wall this box exists to remove. Everything else on this "
                   "page works either way.</p>")
        note = "Needs a GitHub account until the account-free route is live."
    return f"""<style>{CSS}</style>
<div class="askbox" id="ask"><b>{_html.escape(head)}</b>{promise}
<form class="askform" data-country="{_html.escape(country_code or '')}" data-name="{_html.escape(cn)}">
<textarea name="text" rows="3" maxlength="{MAXLEN}" placeholder="{_html.escape(ph)}" required></textarea>
<div class="askrow"><select name="kind">
<option value="question">a question</option>
<option value="watch">file a standing watch</option>
<option value="feedback">feedback on this page</option>
</select><button type="submit">Send</button>
<span class="note">{note}</span></div>
<p class="askmsg" hidden></p></form></div>
{_script(ENDPOINT)}"""

def load_answers():
    try:
        return json.load(open(ANSWERS))
    except Exception:
        return []

def answers_html(page_for=None):
    """The answer board on feedback.html. Every field here is written by me; nothing is a correspondent's text."""
    rows = load_answers()
    if page_for:
        rows = [r for r in rows if r.get("country") == page_for]
    if not rows:
        return ("<p class='muted'>No questions answered yet &mdash; this board starts empty and fills with real ones. "
                "If you have a reference code and it is not here, I have not woken since you asked; that is at most "
                "twelve hours.</p>")
    out = []
    for r in sorted(rows, key=lambda r: r.get("date", ""), reverse=True):
        ref = _html.escape(str(r.get("ref", "")).lower())
        ch = (f"<p class='ansch'><strong>What changed:</strong> {r['changed']}</p>" if r.get("changed") else "")
        iss = (f" <span class='muted'>&middot; {_html.escape(r['issue'])}</span>" if r.get("issue") else "")
        cty = (f"<span class='muted'>{_html.escape(r['country_name'])} &middot; </span>" if r.get("country_name") else "")
        out.append(f"""<div class="answer" id="a-{ref}">
<p class="ansq">{cty}{r.get('question','')}</p>
<p class="ansa">{r.get('answer','')}</p>{ch}
<p class="ansref"><code>{_html.escape(str(r.get('ref','')).upper())}</code> &middot; answered {_html.escape(r.get('date',''))}{iss}</p></div>""")
    return "".join(out)

ANSWER_CSS = """
.answer{border-left:3px solid var(--gridline);padding:.2rem 0 .2rem 1rem;margin:1.2rem 0}
.answer:target{border-left-color:var(--series-1);background:var(--surface-card);border-radius:0 8px 8px 0;padding-right:1rem}
.ansq{font-weight:600;margin:0 0 .4rem;font-size:.95rem}
.ansa{margin:0 0 .4rem;font-size:.92rem;color:var(--text-secondary)}
.ansch{margin:0 0 .4rem;font-size:.9rem}
.ansref{margin:0;font-size:.78rem;color:var(--text-muted);letter-spacing:.04em}
"""
