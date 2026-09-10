#!/usr/bin/env python3
"""Tests for the GETS/MFAT source. No network: the fixtures have the shape of what GETS served on 10 September 2026.

The point of most of these is the promise on the page — that no person's name, address, telephone number or
e-mail address is stored or published from a source that carries all four. Which is why the people in these
fixtures are invented: a test file that proves I do not republish someone's home address is no place to keep a
real one. Company names and their award values are real, because those are the procurement facts this service
exists to publish. Run: python3 mfat_tenders_test.py
"""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mfat_tenders as m
import dfat_notices

F, N = [], 0
def eq(got, want, what):
    global N; N += 1
    if got != want: F.append(f"{what}\n   got  {got!r}\n   want {want!r}")
def ok(cond, what):
    global N; N += 1
    if not cond: F.append(what)

# ---------------------------------------------------------------- outcomes, as served
AWARD_ORG = ("This tender has been awarded. L T MCGUINNESS LIMITED - 4, Example Street, Wellington, Wellington, "
             "Not Applicable, 6011, NEW ZEALAND Value $ 12,000,000 Further Award Information: Construction "
             "Contractor Contract awarded to LT McGuinness as of 31/8/26. Contract value of ~$12,000,000. "
             "Award Date: Monday, 31 August 2026 (Pacific/Auckland UTC+13:00)")
AWARD_PERSON_OF_ORG = ("This tender has been completed. Further information: This contract has been awarded on "
                       "4 September 2026 to Tama Rewiri of Mordros Services Limited. Term of Contract is through "
                       "to 30 September 2029. Date RFx was completed/updated: Tuesday, 9 September 2026 4:55 PM")
AWARD_PERSON = ("This tender has been completed. Further information: This contract has been awarded on 25th "
                "August 2026 to Hana Petersen Term of Contract is through to 15th October 2027 The role is to provide "
                "Revenue Strategy Technical Assistance to the Government of Niue. Date RFx was completed/updated: "
                "Monday, 7 September 2026 10:19 AM")
NOT_AWARDED = ("This tender has been completed. Further information: Please note this role has not been "
               "successfully awarded at this time. We are looking into alternative options. Date RFx was "
               "completed/updated: Wednesday, 9 September 2026 4:59 PM (Pacific/Auckland UTC+12:00)")
SUPERSEDED = ("No Winner This tender opportunity was superseded by GETS listing 33943523. The contract has been "
              "awarded to LT McGuinness. Details of the contract award are available under that listing.")
PERSON_ADDRESS = ("This tender has been awarded to: Sir Alastair Kettleborough - 12, Example Street, Brooklyn, "
                  "Wellington, NEW ZEALAND Exemption under rule: 3. Only one supplier")
SYSTEM = ("This tender has been completed. Further information: Completed by system Date RFx was "
          "completed/updated: Friday, 28 August 2026 11:55 PM (Pacific/Auckland UTC+12:00)")

a = m.classify_outcome(AWARD_ORG)
eq(a["state"], "awarded", "a company award is an award")
eq(a["supplier"], "L T MCGUINNESS LIMITED", "the company is named")
eq(a["value_nzd"], 12000000.0, "the contract value is read")
eq(a["date"], "2026-08-31", "the award date is read")
ok("Example Street" not in str(a) and "6011" not in str(a), "no street address survives a company award")

b = m.classify_outcome(AWARD_PERSON_OF_ORG)
eq(b["state"], "awarded", "person-of-company is an award")
eq(b["supplier"], "Mordros Services Limited", "the contracting entity is kept, the person is not")
ok("Tama" not in str(b) and "Rewiri" not in str(b), "no individual's name in a person-of-company award")

c = m.classify_outcome(AWARD_PERSON)
eq(c["state"], "awarded", "an award to an individual is still an award")
ok("supplier" not in c and c.get("supplier_withheld"), "an individual awardee is withheld, and says so")
ok("Hana" not in str(c) and "Petersen" not in str(c), "no individual's name anywhere in the record")

d = m.classify_outcome(NOT_AWARDED)
eq(d["state"], "not awarded", "'has not been successfully awarded' is not an award")
ok("alternative options" in (d.get("note") or ""), "the reason is kept when it names no one")

e = m.classify_outcome(SUPERSEDED)
eq(e["state"], "superseded", "'No Winner' plus a superseding listing is a supersession")
eq(e["superseded_by"], "33943523", "the superseding listing is kept so a reader can follow it")

f = m.classify_outcome(PERSON_ADDRESS)
ok("Kettleborough" not in str(f) and "Example Street" not in str(f) and "Brooklyn" not in str(f),
   "no name or home address from an award to a titled individual")
ok(f.get("supplier_withheld"), "a titled individual is withheld")

g = m.classify_outcome(SYSTEM)
eq(g["state"], "completed", "a system completion is not an award")
ok("note" not in g, "'Completed by system' is noise, not a note")
eq(m.classify_outcome(""), None, "no outcome block means no outcome")

# ---------------------------------------------------------------- contact stripping in overview text
OVERVIEW = ("MFAT and NRBT are seeking an experienced Technical Adviser.\n"
            "Closing date for applications: 5:00pm (NZ Time) on Tuesday 19th May 2026.\n"
            "For some of the key functions, please see: https://example-jobs.co.nz/job/91769834?ref=search\n"
            "Example Recruitment Limited has been engaged to manage this procurement process. For all correspondence, "
            "queries, or to obtain a copy of the full Position Description, please contact:\n"
            "Morgan Ellery\nPractice Lead, NZ\nPhone: +64 27 000 0000\nEmail: morgan.ellery@example.com")
s = m.strip_contacts(OVERVIEW)
ok("Technical Adviser" in s, "the substance of the overview survives")
ok("Morgan" not in s and "Ellery" not in s, "the named contact does not survive")
ok("@" not in s, "no e-mail address survives")
ok("27 000 0000" not in s, "no telephone number survives")
ok("example-jobs" not in s, "third-party links are not republished")
ok("www.gets.govt.nz/x" in m.strip_contacts("see https://www.gets.govt.nz/x"), "the source's own links are kept")

# ---------------------------------------------------------------- list parsing
ROWS = '''<tr id="tender-34509000" class="tender blueRow">
 <td><a href="UO/ExternalTenderDetails.htm?id=34509000">34509000</a></td>
 <td><a href="x">TR2025-43</a></td><td><a href="x">Owheo Project Furniture Fitout</a></td>
 <td><a href="x"><abbr title="Award Notice">AN</abbr></a></td>
 <td>12:00 AM 19 Nov 2026 (Pacific/Auckland UTC+13:00)</td><td>University of Otago</td></tr>
<tr id="tender-33995584" class="tender greyRow">
 <td><a href="MFAT/ExternalTenderDetails.htm?id=33995584">33995584</a></td>
 <td><a href="x">[None]</a></td><td><a href="x">Technical Adviser for National Reserve Bank of Tonga</a></td>
 <td><a href="x"><abbr title="Registration of Interest">ROI</abbr></a></td>
 <td>4:59 PM 9 Sep 2026 (Pacific/Auckland UTC+12:00)</td><td>Ministry of Foreign Affairs and Trade</td></tr>
<tr id="tender-34444444" class="tender blueRow">
 <td><a href="KO/ExternalTenderDetails.htm?id=34444444">34444444</a></td>
 <td><a href="x">R1</a></td><td><a href="x">HDS Main Contractor for Bankwood &amp; Tongariro Project, Hamilton</a></td>
 <td><a href="x">RFP</a></td><td>1 Sep 2026</td><td>Kāinga Ora</td></tr>'''
rows = [dict(zip(("id","ref","title","type","date_label","org"), (t, c[1], c[2], c[3], c[4], c[5])))
        for t, c in [(t, [m.text(x) for x in m.CELL.findall(b)]) for t, b in m.ROW.findall(ROWS)]]
eq(len(rows), 3, "three rows parse")
eq(rows[1]["title"], "Technical Adviser for National Reserve Bank of Tonga", "the title cell is the title")
eq(rows[0]["ref"], "TR2025-43", "the reference cell is the reference")
ok(m.HINT.search(rows[1]["title"]), "an MFAT Pacific title is a hint")
ok(not m.HINT.search(rows[0]["title"]), "a university furniture fitout is not")
ok(not m.HINT.search(rows[2]["title"]), "'Tongariro' is not Tonga")
eq(m.DETAIL.search(m.ROW.findall(ROWS)[1][1]).group(1), "MFAT/ExternalTenderDetails.htm?id=33995584", "the detail link is found")

# ---------------------------------------------------------------- the keep rule
ok(m.pacific_relevant({"title": "Relief Supplies Logistics (2026 - 2035)", "dept": "Crown Funding", "regions": "Auckland"}),
   "an aid-budget tender is kept even when its title names no country")
ok(m.pacific_relevant({"title": "Advance Notice: Vanuatu Resilient Education Infrastructure", "dept": None, "regions": None}),
   "a Pacific title is kept whatever the business unit")
ok(not m.pacific_relevant({"title": "Sir Alastair Kettleborough", "dept": "Departmental", "regions": "New Zealand"}),
   "a domestic departmental tender is dropped, name and all")

# ---------------------------------------------------------------- country matching, shared with the DFAT source
AL = {"TO": ["Tonga"], "VU": ["Vanuatu"], "CK": ["Cook Islands"], "NU": ["Niue"], "FJ": ["Fiji"]}
tonga = {"title": "Technical Adviser for National Reserve Bank of Tonga", "summary": ""}
tongariro = {"title": "HDS Main Contractor for Bankwood & Tongariro Project", "summary": ""}
regional = {"title": "RFP: Scoping Study for a Renewable Energy Upgrade Programme for the Pacific", "summary": ""}
ok(dfat_notices.matches(tonga, "TO", AL), "a Tonga tender matches Tonga")
ok(not dfat_notices.matches(tongariro, "TO", AL), "a Tongariro tender does not match Tonga")
ok(not dfat_notices.matches(tonga, "FJ", AL), "a Tonga tender does not match Fiji")
ok(dfat_notices.regional(regional, AL), "a Pacific-wide tender is regional")
ok(not dfat_notices.regional(tonga, AL), "a country tender is not regional")
nz = {"tenders": [tonga | {"id": "1"}, regional | {"id": "2"}, tongariro | {"id": "3"}]}
cn, rn = m.for_country(nz, "TO", AL)
eq([t["id"] for t in cn], ["1"], "for_country returns the country's tenders")
eq([t["id"] for t in rn], ["2"], "for_country returns Pacific-wide tenders separately")
eq(m.for_country(None, "TO", AL), ([], []), "no GETS block means no tenders, not a crash")

print(f"{N - len(F)}/{N} passed")
for x in F: print("FAIL:", x)
sys.exit(1 if F else 0)
