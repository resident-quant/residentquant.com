"""Generate the synthetic "Satellite autonomy ops" warehouse for ResidentQuant Live.

Fully synthetic. Modeled on what spacecraft autonomy companies publicly describe:
onboard detection of resident space objects (RSOs) with star trackers and cameras,
conjunction screening, autonomous collision avoidance, formation flying, RPO and
alternative navigation (alt-PNT) when GNSS is jammed. Every customer, spacecraft and
object is invented.

Planted stories (for demos):
  1. 2026-08-14: a rocket body at ~545 km, 97.6 deg breaks up. Fragments enter the
     public catalog over ~3 weeks. Detections, unmatched detections, conjunctions,
     avoidance maneuvers and delta-v rise for sun-synchronous spacecraft near 545 km.
  2. Firmware v3.2 rolls out in rings (Sep 15 to Oct 3, 2026). It raises catalog match
     rate everywhere, but on ST-200 star trackers (Polaris dawn-dusk ring, last ring,
     Oct 2-3) it raises false alarms at sun angles under 45 deg (stray light).
  3. GNSS jamming grows from Jul 2026 with a big episode Oct 6-11, 2026. Missions with
     alt-PNT hold navigation error; Lumen Connect has alt-PNT off and its error jumps.
  4. Lumen Connect turns on autonomous collision avoidance on Oct 5, 2026, so the
     autonomous decision share jumps that week.

Run:  python3 _generate.py   (writes parquet + catalog.json + semantic.json here)
"""
import json, os, datetime as dt
import numpy as np, pandas as pd, duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
rng = np.random.default_rng(20261013)
START, END = pd.Timestamp("2025-03-01"), pd.Timestamp("2026-10-11")
BREAKUP = pd.Timestamp("2026-08-14")
AS_OF = "2026-10-11"
D = lambda s: pd.Timestamp(s)

# ---------------------------------------------------------------- customers
customers = pd.DataFrame([
    ("C01", "Polaris EO", "Commercial Earth observation constellation", "commercial", "2025-05-12", "2026-02-02", 26_000, 120_000, True, 536_000),
    ("C02", "Kestrel Swarm", "Civil agency 4-cubesat swarm (vision nav, SSA)", "civil", "2025-06-16", "2025-07-01", 250_000, 0, True, 1_000_000),
    ("C03", "Vanguard SDA", "Space domain awareness and alt-PNT", "defense", "2025-07-28", "2025-12-01", 310_000, 640_000, False, 3_100_000),
    ("C04", "Tether Servicing", "GEO servicing and RPO (defense prime program)", "defense (via prime)", "2025-08-04", "2025-10-01", 900_000, 1_100_000, False, 1_800_000),
    ("C05", "Lumen Connect", "Broadband mega-constellation", "commercial", "2025-12-15", "2026-10-05", 14_000, 0, True, 168_000),
], columns=["customer_id", "customer_name", "mission_type", "segment", "contract_start",
            "autonomous_ca_enabled_date", "license_per_satellite_usd", "hardware_passthrough_usd",
            "data_sharing_agreement", "annual_contract_value_usd"])
customers["contract_start"] = pd.to_datetime(customers["contract_start"]).dt.date
customers["autonomous_ca_enabled_date"] = pd.to_datetime(customers["autonomous_ca_enabled_date"]).dt.date
AUTO = {r.customer_id: (pd.Timestamp(r.autonomous_ca_enabled_date) if pd.notna(r.autonomous_ca_enabled_date) else None)
        for r in customers.itertuples()}

# ---------------------------------------------------------------- spacecraft
# (customer, prefix, count per launch, launch dates, orbit_class, alt, inc, sensor, product, bus, altpnt)
groups = [
    ("C02", "KESTREL", [("2023-07-18", 4)], "SSO midday", 575, 97.7, "ST-100 star tracker", "Era-Core", "6U cubesat", True),
    ("C01", "POLARIS", [("2025-06-23", 4), ("2025-11-10", 2), ("2026-04-15", 2)], "SSO midday", 530, 97.5, "HDR camera", "Era-Node", "ESPA smallsat", True),
    ("C01", "POLARIS", [("2025-06-23", 2), ("2025-11-10", 3), ("2026-04-15", 3)], "SSO dawn-dusk", 545, 97.6, "ST-200 star tracker", "Era-Core", "ESPA smallsat", True),
    ("C03", "VANGUARD", [("2025-08-18", 4), ("2026-01-20", 4)], "LEO 53 deg", 500, 53.0, "HDR camera", "Era-Node", "150 kg smallsat", True),
    ("C04", "TETHER", [("2025-09-05", 2)], "GEO", 35786, 0.1, "HDR camera", "Era-Node", "GEO servicer", True),
    ("C05", "LUMEN", [("2026-01-20", 6), ("2026-06-22", 6)], "LEO 53 deg", 550, 53.0, "ST-100 star tracker", "Era-Core", "ESPA smallsat", False),
    ("C03", "VANGUARD-G", [("2026-03-02", 2)], "GEO", 35786, 0.05, "ST-100 star tracker", "Era-Core", "GEO smallsat", True),
]
BUS = {"3U cubesat": (5, 65), "6U cubesat": (12, 65), "ESPA smallsat": (180, 220),
       "150 kg smallsat": (150, 220), "GEO servicer": (950, 300), "GEO smallsat": (420, 300)}
rows, counters = [], {}
for cust, prefix, launches, oc, alt, inc, sensor, product, bus, altpnt in groups:
    for ld, n in launches:
        for _ in range(n):
            counters[prefix] = counters.get(prefix, 0) + 1
            launch = D(ld)
            comm = launch + pd.Timedelta(days=int(rng.integers(21, 36)))
            a = alt + rng.normal(0, 4) if oc != "GEO" else 35786.0
            rows.append(dict(customer_id=cust, spacecraft_name=f"{prefix}-{counters[prefix]:02d}", orbit_class=oc,
                             orbit_regime="GEO" if oc == "GEO" else "LEO", altitude_km=round(a, 1),
                             inclination_deg=round(inc + rng.normal(0, 0.05), 2), sensor=sensor, era_product=product,
                             bus_class=bus, dry_mass_kg=BUS[bus][0], isp_s=BUS[bus][1], altpnt_enabled=altpnt,
                             launch_date=launch.date(), commissioning_date=comm.date()))
sc = pd.DataFrame(rows).sort_values(["launch_date", "spacecraft_name"]).reset_index(drop=True)
sc.insert(0, "spacecraft_id", [f"SC-{i+1:03d}" for i in range(len(sc))])
sc["status"] = "operational"
sc["module_size_u"] = np.where(sc.era_product == "Era-Node", np.where(sc.orbit_regime == "GEO", 3, 1), np.nan)
sc["camera_count"] = np.where(sc.era_product == "Era-Node", np.where(sc.orbit_regime == "GEO", 3, 1), 0)
sc["software_host"] = np.where(sc.era_product == "Era-Node", "Era-Node flight computer (FPGA)", "star tracker processor")
cstart = dict(zip(customers.customer_id, pd.to_datetime(customers.contract_start)))
sc["data_start_date"] = [max(D(c), cstart[k]).date() for c, k in zip(sc.commissioning_date, sc.customer_id)]
sc = sc.merge(customers[["customer_id", "customer_name"]], on="customer_id")
assert len(sc) == 44

# firmware rollout per spacecraft
def fw_dates(r):
    ring3 = r.orbit_class == "SSO dawn-dusk"
    ring1 = r.customer_id in ("C02", "C06")
    s = int(r.spacecraft_id[3:])
    v30 = D("2025-11-17") + pd.Timedelta(days=s % 12)
    v31 = D("2026-03-16") + pd.Timedelta(days=s % 12)
    if ring1: v32 = D("2026-09-15") + pd.Timedelta(days=s % 2)
    elif ring3: v32 = D("2026-10-02") + pd.Timedelta(days=s % 2)
    else: v32 = D("2026-09-21") + pd.Timedelta(days=s % 5)
    return [("v2.4", D("2000-01-01")), ("v3.0", v30), ("v3.1", v31), ("v3.2", v32)]
FW = {r.spacecraft_id: fw_dates(r) for r in sc.itertuples()}
def fw_on(sid, days):
    out = np.full(len(days), "v2.4", dtype=object)
    for v, d0 in FW[sid]:
        out[days >= d0] = v
    return out

# ---------------------------------------------------------------- resident space objects
n_bg = 5800
leo = rng.random(n_bg) < 0.86
otype = rng.choice(["payload", "payload", "payload_inactive", "rocket_body", "debris", "debris", "debris"], n_bg)
perigee = np.where(leo, np.clip(rng.normal(620, 160, n_bg), 300, 1400), 35786 + rng.normal(0, 60, n_bg))
apogee = perigee + np.where(leo, np.abs(rng.normal(0, 40, n_bg)), np.abs(rng.normal(0, 30, n_bg)))
incl = np.where(leo, rng.choice([53.0, 97.6, 70.0, 87.9, 43.0, 98.7, 65.0], n_bg) + rng.normal(0, 1.2, n_bg), np.abs(rng.normal(0.5, 1.5, n_bg)))
size = np.where(otype == "debris", rng.choice(["small", "small", "medium"], n_bg),
                np.where(otype == "rocket_body", "large", rng.choice(["medium", "large"], n_bg)))
first_cat = pd.to_datetime(rng.integers(D("1967-01-01").value // 10**9, D("2025-01-01").value // 10**9, n_bg), unit="s").normalize()
owner = rng.choice(["US", "US", "US", "CN", "CN", "RU", "RU", "EU", "JP", "IN", "Other"], n_bg)
cat_no = np.sort(rng.choice(np.arange(10000, 66000), n_bg, replace=False))
rso_bg = pd.DataFrame(dict(rso_id=cat_no, object_type=otype, size_class=size, owner_country=owner,
                           perigee_km=perigee.round(1), apogee_km=apogee.round(1), inclination_deg=incl.round(2),
                           first_cataloged=first_cat.date, parent_event=None, is_fragment=False))
# the breakup parent and its fragments
parent_id = 48217
rso_bg.loc[len(rso_bg)] = dict(rso_id=parent_id, object_type="rocket_body", size_class="large", owner_country="Other",
                               perigee_km=541.2, apogee_km=549.8, inclination_deg=97.6, first_cataloged=dt.date(2021, 5, 3),
                               parent_event=None, is_fragment=False)
n_frag = 420
lag = np.clip(rng.gamma(2.0, 6.0, n_frag), 2, 57).astype(int)  # days after breakup to enter the public catalog
frag = pd.DataFrame(dict(rso_id=np.arange(66001, 66001 + n_frag), object_type="debris",
                         size_class=rng.choice(["small", "small", "small", "medium"], n_frag), owner_country="Other",
                         perigee_km=np.clip(rng.normal(545, 28, n_frag), 470, 640).round(1),
                         apogee_km=np.clip(rng.normal(560, 40, n_frag), 480, 720).round(1),
                         inclination_deg=(97.6 + rng.normal(0, 0.25, n_frag)).round(2),
                         first_cataloged=(BREAKUP + pd.to_timedelta(lag, "D")).date,
                         parent_event="RB 48217 breakup 2026-08-14", is_fragment=True))
frag["apogee_km"] = np.maximum(frag.apogee_km, frag.perigee_km)
rso = pd.concat([rso_bg, frag], ignore_index=True)
rso["object_name"] = np.where(rso.is_fragment, "RB 48217 DEB", np.where(rso.object_type == "rocket_body", "R/B",
                     np.where(rso.object_type == "debris", "DEB", "PAYLOAD"))) + " " + rso.rso_id.astype(str)
rso.loc[rso.rso_id == parent_id, "object_name"] = "RB 48217 (fragmented 2026-08-14)"
rso = rso[["rso_id", "object_name", "object_type", "size_class", "owner_country", "perigee_km", "apogee_km",
           "inclination_deg", "first_cataloged", "is_fragment", "parent_event"]]
rso_leo = rso[(rso.perigee_km < 2000) & (~rso.is_fragment)].rso_id.values
rso_geo = rso[rso.perigee_km > 30000].rso_id.values
frag_ids, frag_cat = frag.rso_id.values, pd.to_datetime(frag.first_cataloged).values

# ---------------------------------------------------------------- helpers
def breakup_ramp(days):
    t = (days - BREAKUP).days.values.astype(float)
    r = np.where(t < 0, 0, np.minimum(t / 21.0, 1.0) * np.exp(-np.maximum(t - 21, 0) / 290))
    return r
def affect(r):
    if r.orbit_class.startswith("SSO"): return 1.0 if 515 <= r.altitude_km <= 580 else 0.5
    if r.orbit_class == "LEO 53 deg": return 0.3
    return 0.0
def rand_times(days_rep):
    return days_rep + pd.to_timedelta(rng.integers(0, 86400, len(days_rep)), "s")

det_parts, conj_parts, man_parts, nav_parts = [], [], [], []
conj_seq = 0
for r in sc.itertuples():
    days = pd.date_range(max(START, D(r.data_start_date)), END, freq="D")
    if len(days) == 0: continue
    n = len(days); geo = r.orbit_regime == "GEO"; aff = affect(r); ramp = breakup_ramp(days)
    growth = 1 + 0.15 * (days - START).days.values / 365
    fw = fw_on(r.spacecraft_id, days)
    auto0 = AUTO[r.customer_id]
    auto_on = np.zeros(n, bool) if auto0 is None else (days >= auto0)

    # ---------- nav daily
    tt = (days - START).days.values
    jam_lam = np.where(geo, 0.0, 3 + 5 * np.clip((days - D("2026-07-01")).days.values / 90, 0, 1))
    jam_lam = jam_lam * np.where(r.orbit_class == "LEO 53 deg", 1.4, 1.0)
    episode = (days >= D("2026-10-06")) & (days <= D("2026-10-11"))
    jam_lam = jam_lam + np.where(episode & (not geo), 34 if r.orbit_class == "LEO 53 deg" else 11, 0)
    jam = rng.poisson(jam_lam)
    outage = jam + (rng.integers(0, 4, n) if not geo else rng.integers(380, 620, n))
    altpnt_min = outage if r.altpnt_enabled else np.zeros(n, int)
    p50 = (24 if geo else 3.6) * np.exp(rng.normal(0, 0.15, n))
    if r.altpnt_enabled:
        p95 = (58 if geo else 9.5) * np.exp(rng.normal(0, 0.12, n)) + 0.05 * jam
    else:
        p95 = (9.5 * np.exp(rng.normal(0, 0.12, n)) + np.minimum(2.6 * jam, 600)) if not geo else 140 + rng.normal(0, 10, n)
    up = np.ones(n)
    for k in np.where(rng.random(n) < 1 / 260)[0]:
        up[k:k + rng.integers(1, 4)] = rng.uniform(0, 0.6)
    nav_parts.append(pd.DataFrame(dict(nav_date=days.date, spacecraft_id=r.spacecraft_id, firmware_version=fw,
        gnss_available_pct=np.clip(1 - outage / 1440, 0, 1).round(4), jamming_minutes=jam,
        gnss_outage_minutes=outage, altpnt_minutes=altpnt_min, pos_error_p50_m=p50.round(2),
        pos_error_p95_m=p95.round(2), uptime_pct=up.round(3))))

    # ---------- detections
    base = {"HDR camera": 15.0, "ST-100 star tracker": 6.5, "ST-200 star tracker": 6.0}[r.sensor]
    lam = base * (0.5 if geo else 1.0) * growth * (1 + 0.7 * aff * ramp) * up
    cnt = rng.poisson(lam)
    di = np.repeat(np.arange(n), cnt); m = len(di)
    ts = rand_times(days[di])
    fwd = fw[di]
    dd = r.orbit_class == "SSO dawn-dusk"
    sun = 20 + 160 * (rng.beta(1.4, 4.0, m) if dd else rng.beta(2, 2, m))
    rng_km = np.clip(np.exp(rng.normal(np.log(2600 if geo else 380), 0.8, m)), 4, 9000)
    fa_base = {"HDR camera": 0.02, "ST-100 star tracker": 0.034, "ST-200 star tracker": 0.04}[r.sensor]
    fa_p = np.where(fwd == "v3.2", fa_base * 0.7, fa_base)
    if r.sensor == "ST-200 star tracker":
        fa_p = np.where((fwd == "v3.2") & (sun < 45), 0.36, fa_p)
    is_fa = rng.random(m) < fa_p
    frag_share = 0.33 * aff * ramp[di]
    is_frag = (~is_fa) & (rng.random(m) < frag_share)
    match_p = pd.Series(fwd).map({"v2.4": 0.74, "v3.0": 0.80, "v3.1": 0.84, "v3.2": 0.905}).values
    if r.sensor == "ST-200 star tracker":
        match_p = np.where((fwd == "v3.2") & (sun < 45), 0.70, match_p)
    status = np.where(is_fa, "false_alarm", "unmatched").astype(object)
    rso_id = np.full(m, np.nan)
    # fragments: matched only if in the public catalog for 7+ days (weekly onboard catalog upload)
    fi = np.where(is_frag)[0]
    if len(fi):
        pick = rng.integers(0, len(frag_ids), len(fi))
        known = frag_cat[pick] + np.timedelta64(7, "D") <= ts.values[fi]
        ok = known & (rng.random(len(fi)) < match_p[fi])
        status[fi[ok]] = "matched"; rso_id[fi[ok]] = frag_ids[pick[ok]]
    oi = np.where((~is_fa) & (~is_frag))[0]
    ok = rng.random(len(oi)) < match_p[oi]
    status[oi[ok]] = "matched"; pool = rso_geo if geo else rso_leo
    rso_id[oi[ok]] = rng.choice(pool, ok.sum())
    lat_base = pd.Series(fwd).map({"v2.4": 420, "v3.0": 310, "v3.1": 245, "v3.2": 185}).values * (0.8 if r.sensor == "HDR camera" else 1.0)
    mag = 6 + 5 * np.log10(rng_km / 500) + rng.normal(0, 1.1, m)
    det_parts.append(pd.DataFrame(dict(spacecraft_id=r.spacecraft_id, detected_at=ts, sensor=r.sensor,
        firmware_version=fwd, match_status=status, rso_id=rso_id, range_km=rng_km.round(1),
        visual_magnitude=mag.round(2), sun_angle_deg=sun.round(1),
        onboard_latency_ms=(lat_base * rng.gamma(4, 0.25, m)).round(0).astype(int))))

    # ---------- conjunctions
    c_base = 0.03 if geo else {500: 0.17, 520: 0.21, 530: 0.23, 545: 0.26, 550: 0.24, 575: 0.25}.get(
        min([500, 520, 530, 545, 550, 575], key=lambda a: abs(a - r.altitude_km)), 0.22)
    c_lam = c_base * growth * (1 + 2.3 * aff * ramp) * np.where(up > 0.5, 1, 0.6)
    cc = rng.poisson(c_lam); ci = np.repeat(np.arange(n), cc); k = len(ci)
    if k:
        scr = rand_times(days[ci])
        tca = scr + pd.to_timedelta(rng.uniform(8, 96, k), "h")
        miss = np.clip(np.exp(rng.normal(np.log(4000), 1.1, k)), 15, 40000)
        pc = np.minimum(2e-3 * np.exp(-miss / 260) * np.exp(rng.normal(0, 0.5, k)), 8e-3)
        tier = np.where(pc >= 1e-4, "high", np.where(pc >= 1e-5, "medium", "low"))
        fragp = (2.3 * aff * ramp[ci]) / (1 + 2.3 * aff * ramp[ci])
        use_frag = rng.random(k) < fragp
        rid = np.where(use_frag, rng.choice(frag_ids, k), rng.choice(rso_geo if geo else rso_leo, k))
        a_on = auto_on[ci]
        source = np.where(a_on & (rng.random(k) < 0.68), "onboard", "ground_cdm")
        mode = np.where(tier == "low", None, np.where(a_on, "autonomous", "ground")).astype(object)
        act = np.where(tier == "high", np.where(rng.random(k) < 0.93, "maneuver", "monitor"),
               np.where(tier == "medium", np.where(rng.random(k) < np.where(a_on, 0.07, 0.17), "maneuver", "monitor"), "none"))
        lat = np.where(tier == "low", np.nan, np.where(a_on, np.exp(rng.normal(np.log(2.4), 0.5, k)),
                                                       np.exp(rng.normal(np.log(290), 0.7, k))))
        ids = [f"CJ-{conj_seq + i + 1:06d}" for i in range(k)]; conj_seq += k
        cdf = pd.DataFrame(dict(conjunction_id=ids, spacecraft_id=r.spacecraft_id, rso_id=rid, screened_at=scr,
            tca=tca, miss_distance_m=miss.round(1), radial_sep_m=(miss * rng.uniform(0.05, 0.6, k)).round(1),
            collision_probability=pc, risk_tier=tier, source=source, decision_mode=mode, action=act,
            decision_latency_min=np.round(lat, 2)))
        conj_parts.append(cdf)
        # collision-avoidance maneuvers
        mc = cdf[cdf.action == "maneuver"]
        if len(mc):
            auto = (mc.decision_mode == "autonomous").values
            lead = np.where(auto, rng.uniform(1, 6, len(mc)), rng.uniform(2, 12, len(mc)))
            dv = np.exp(rng.normal(np.log(0.30 if geo else 0.12), 0.5, len(mc)))
            man_parts.append(pd.DataFrame(dict(spacecraft_id=r.spacecraft_id, executed_at=mc.tca.values - pd.to_timedelta(lead, "h").values,
                purpose="collision_avoidance", conjunction_id=mc.conjunction_id.values, autonomous=auto, planned_dv_mps=dv)))
    # station keeping / formation keeping / RPO
    sk_every = 7 if geo else 18
    sk_days = days[::sk_every][1:] + pd.to_timedelta(rng.integers(0, 3, len(days[::sk_every][1:])), "D")
    sk_days = sk_days[sk_days <= END]
    sdv = np.exp(rng.normal(np.log(0.45 if geo else 0.04), 0.35, len(sk_days)))
    man_parts.append(pd.DataFrame(dict(spacecraft_id=r.spacecraft_id, executed_at=rand_times(sk_days), purpose="station_keeping",
        conjunction_id=None, autonomous=auto_on[np.searchsorted(days, sk_days.normalize()).clip(0, n - 1)], planned_dv_mps=sdv)))
    if r.customer_id == "C02":
        fk = days[rng.random(n) < 0.5]
        man_parts.append(pd.DataFrame(dict(spacecraft_id=r.spacecraft_id, executed_at=rand_times(fk), purpose="formation_keeping",
            conjunction_id=None, autonomous=True, planned_dv_mps=np.exp(rng.normal(np.log(0.008), 0.4, len(fk))))))
    if r.customer_id == "C04":
        camp = days[((days >= D("2026-02-09")) & (days <= D("2026-02-23"))) | ((days >= D("2026-07-06")) & (days <= D("2026-07-20")))]
        camp = camp.repeat(3)
        man_parts.append(pd.DataFrame(dict(spacecraft_id=r.spacecraft_id, executed_at=rand_times(camp), purpose="rpo_approach",
            conjunction_id=None, autonomous=True, planned_dv_mps=np.exp(rng.normal(np.log(0.15), 0.5, len(camp))))))

# ---------------------------------------------------------------- assemble raw tables
det = pd.concat(det_parts, ignore_index=True).sort_values("detected_at").reset_index(drop=True)
det.insert(0, "detection_id", [f"DT-{i+1:07d}" for i in range(len(det))])
det["rso_id"] = det.rso_id.astype("Int64")

conj = pd.concat(conj_parts, ignore_index=True).sort_values("screened_at").reset_index(drop=True)
# ground CDM feed resends ~2% of messages: duplicate rows with a later screened_at
dup = conj[(conj.source == "ground_cdm") & (rng.random(len(conj)) < 0.02)].copy()
dup["screened_at"] = dup.screened_at + pd.to_timedelta(rng.integers(20, 180, len(dup)), "min")
conj_raw = pd.concat([conj, dup], ignore_index=True).sort_values("screened_at").reset_index(drop=True)

man = pd.concat(man_parts, ignore_index=True)
man = man.merge(sc[["spacecraft_id", "dry_mass_kg", "isp_s"]], on="spacecraft_id")
err = np.where(man.autonomous, 0.015, 0.035)
man["executed_dv_mps"] = (man.planned_dv_mps * (1 + rng.normal(0, err))).round(5)
man["planned_dv_mps"] = man.planned_dv_mps.round(5)
man["propellant_g"] = (man.dry_mass_kg * (1 - np.exp(-man.executed_dv_mps / (man.isp_s * 9.80665))) * 1000).round(2)
man = man[man.executed_at <= END + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)]
man = man.drop(columns=["dry_mass_kg", "isp_s"]).sort_values("executed_at").reset_index(drop=True)
man.insert(0, "maneuver_id", [f"MV-{i+1:06d}" for i in range(len(man))])
man["autonomous"] = man.autonomous.astype(bool)

nav = pd.concat(nav_parts, ignore_index=True)

# ---------------------------------------------------------------- write raw + aggregates with DuckDB
con = duckdb.connect()
for name, df in dict(dim_customers=customers, dim_spacecraft=sc.drop(columns=["customer_name"]), dim_rso=rso,
                     fct_detections=det, fct_conjunctions=conj_raw, fct_maneuvers=man, fct_nav_daily=nav).items():
    con.register("df_" + name, df)
    con.execute(f"CREATE TABLE {name} AS SELECT * FROM df_{name}")
con.execute("ALTER TABLE dim_customers ALTER contract_start TYPE DATE")
con.execute("ALTER TABLE dim_customers ALTER autonomous_ca_enabled_date TYPE DATE")
con.execute("ALTER TABLE dim_spacecraft ALTER launch_date TYPE DATE")
con.execute("ALTER TABLE dim_spacecraft ALTER commissioning_date TYPE DATE")
con.execute("ALTER TABLE dim_rso ALTER first_cataloged TYPE DATE")
con.execute("ALTER TABLE fct_nav_daily ALTER nav_date TYPE DATE")
SCV = "(SELECT s.*, c.customer_name FROM dim_spacecraft s JOIN dim_customers c USING (customer_id))"
con.execute(f"""CREATE TABLE agg_detections_daily AS
SELECT d.detected_at::DATE AS detection_date, s.customer_name, s.orbit_class, d.sensor, d.firmware_version,
  CASE WHEN d.sun_angle_deg < 45 THEN 'under 45 deg' WHEN d.sun_angle_deg < 90 THEN '45 to 90 deg' ELSE '90 deg and over' END AS sun_angle_band,
  COUNT(*) AS detections, COUNT(*) FILTER (WHERE match_status='matched') AS matched,
  COUNT(*) FILTER (WHERE match_status='unmatched') AS unmatched, COUNT(*) FILTER (WHERE match_status='false_alarm') AS false_alarms,
  SUM(onboard_latency_ms) AS latency_ms_sum
FROM fct_detections d JOIN {SCV} s USING (spacecraft_id) GROUP BY ALL ORDER BY 1""")
con.execute(f"""CREATE TABLE agg_conjunctions_daily AS
WITH c AS (SELECT * FROM fct_conjunctions QUALIFY ROW_NUMBER() OVER (PARTITION BY conjunction_id ORDER BY screened_at)=1)
SELECT c.screened_at::DATE AS screened_date, s.customer_name, s.orbit_class,
  CASE WHEN s.orbit_regime='GEO' THEN 'GEO' WHEN s.altitude_km < 525 THEN 'under 525 km' WHEN s.altitude_km <= 560 THEN '525 to 560 km' ELSE 'over 560 km' END AS altitude_band,
  c.risk_tier, c.source, COALESCE(c.decision_mode,'none') AS decision_mode, c.action,
  CASE WHEN r.is_fragment THEN 'breakup fragment' ELSE r.object_type END AS object_type,
  COUNT(*) AS conjunctions, COUNT(*) FILTER (WHERE risk_tier='high') AS high_risk,
  COUNT(*) FILTER (WHERE risk_tier<>'low') AS decisions, COUNT(*) FILTER (WHERE decision_mode='autonomous') AS autonomous_decisions,
  COUNT(*) FILTER (WHERE action='maneuver') AS maneuvers_triggered, SUM(decision_latency_min) AS decision_latency_min_sum
FROM c JOIN {SCV} s USING (spacecraft_id) JOIN dim_rso r USING (rso_id) GROUP BY ALL ORDER BY 1""")
con.execute(f"""CREATE TABLE agg_maneuvers_daily AS
SELECT m.executed_at::DATE AS maneuver_date, s.customer_name, s.orbit_class, m.purpose, m.autonomous,
  COUNT(*) AS maneuvers, SUM(executed_dv_mps) AS delta_v_mps, SUM(propellant_g) AS propellant_g,
  SUM(ABS(executed_dv_mps-planned_dv_mps)/planned_dv_mps) AS dv_error_sum
FROM fct_maneuvers m JOIN {SCV} s USING (spacecraft_id) GROUP BY ALL ORDER BY 1""")
con.execute(f"""CREATE TABLE agg_nav_daily AS
SELECT n.nav_date, s.customer_name, s.orbit_class, s.altpnt_enabled,
  COUNT(*) AS spacecraft_days, SUM(jamming_minutes) AS jamming_minutes, SUM(gnss_outage_minutes) AS gnss_outage_minutes,
  SUM(altpnt_minutes) AS altpnt_minutes, SUM(pos_error_p95_m) AS pos_error_p95_sum, SUM(uptime_pct) AS uptime_sum
FROM fct_nav_daily n JOIN {SCV} s USING (spacecraft_id) GROUP BY ALL ORDER BY 1""")

TABLES = ["dim_customers", "dim_spacecraft", "dim_rso", "fct_detections", "fct_conjunctions", "fct_maneuvers", "fct_nav_daily"]
AGGS = ["agg_detections_daily", "agg_conjunctions_daily", "agg_maneuvers_daily", "agg_nav_daily"]
for t in TABLES + AGGS:
    con.execute(f"COPY {t} TO '{HERE}/{t}.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)")
q = lambda s: con.execute(s).fetchone()[0]
size = lambda t: os.path.getsize(f"{HERE}/{t}.parquet")
rows_of = lambda t: q(f"SELECT COUNT(*) FROM {t}")

# ---------------------------------------------------------------- catalog.json
DOCS = {
 "dim_customers": ("One row per customer mission.", "One row per customer", "customer_id", None, {
   "customer_id": "Customer key", "customer_name": "Customer (invented)", "mission_type": "What the customer flies",
   "segment": "commercial, civil, defense or academic", "contract_start": "Contract start date",
   "autonomous_ca_enabled_date": "Date the customer let spacecraft decide collision avoidance onboard; null if never",
   "license_per_satellite_usd": "Yearly software license per satellite, USD", "hardware_passthrough_usd": "Cameras and modules resold at cost, USD (no margin)",
   "data_sharing_agreement": "Customer shares onboard data back for model tuning and space traffic intelligence",
   "annual_contract_value_usd": "Annual contract value, USD"}),
 "dim_spacecraft": ("One row per customer spacecraft carrying the autonomy software or module.", "One row per spacecraft", "spacecraft_id", "commissioning_date", {
   "spacecraft_id": "Spacecraft key", "customer_id": "Customer key", "spacecraft_name": "Spacecraft name",
   "orbit_class": "SSO dawn-dusk, SSO midday, LEO 53 deg or GEO", "orbit_regime": "LEO or GEO",
   "altitude_km": "Mean altitude, km", "inclination_deg": "Orbit inclination, degrees",
   "sensor": "Onboard sensor used for detection: HDR camera, ST-100 or ST-200 star tracker",
   "era_product": "Era-Node (camera + processor module) or Era-Core (software only)", "bus_class": "Spacecraft bus",
   "dry_mass_kg": "Mass, kg", "isp_s": "Thruster specific impulse, s", "altpnt_enabled": "Alternative navigation (works without GNSS) is turned on",
   "launch_date": "Launch date", "commissioning_date": "Date operations began", "status": "operational",
   "module_size_u": "Era-Node module volume in U (1U = 10 cm cube); null for software only", "camera_count": "Cameras in the Era-Node module",
   "software_host": "Where the autonomy software runs", "data_start_date": "First day in this data: later of commissioning and contract start"}),
 "dim_rso": ("Resident space object catalog: tracked objects in orbit (payloads, rocket bodies, debris).", "One row per tracked object", "rso_id", "first_cataloged", {
   "rso_id": "Catalog number", "object_name": "Object name", "object_type": "payload, payload_inactive, rocket_body or debris",
   "size_class": "small, medium or large", "owner_country": "Owner", "perigee_km": "Perigee altitude, km", "apogee_km": "Apogee altitude, km",
   "inclination_deg": "Inclination, degrees", "first_cataloged": "Date the object entered the public catalog",
   "is_fragment": "Fragment from a known breakup event", "parent_event": "Breakup event the fragment came from"}),
 "fct_detections": ("Objects detected by onboard sensors and the onboard attempt to identify them against the onboard catalog.", "One row per detection", "detection_id", "detected_at", {
   "detection_id": "Detection key", "spacecraft_id": "Spacecraft key", "detected_at": "Detection time, UTC", "sensor": "Sensor that saw it",
   "firmware_version": "Era-Core firmware running at detection time", "match_status": "matched (identified), unmatched (real object, not in onboard catalog) or false_alarm (no object)",
   "rso_id": "Identified object; null unless matched", "range_km": "Estimated range, km", "visual_magnitude": "Apparent brightness (lower is brighter)",
   "sun_angle_deg": "Angle between sensor boresight and the Sun, degrees", "onboard_latency_ms": "Time from image to identification, ms"}),
 "fct_conjunctions": ("Close approaches screened for each spacecraft and the decision taken.", "One row per screening message (see caveats on repeats)", "conjunction_id", "screened_at", {
   "conjunction_id": "Conjunction key", "spacecraft_id": "Spacecraft key", "rso_id": "Other object", "screened_at": "Screening time, UTC",
   "tca": "Time of closest approach, UTC", "miss_distance_m": "Predicted miss distance, m", "radial_sep_m": "Radial separation, m",
   "collision_probability": "Probability of collision (Pc)", "risk_tier": "high (Pc >= 1e-4), medium (>= 1e-5) or low",
   "source": "onboard (own screening) or ground_cdm (ground conjunction data message)", "decision_mode": "autonomous (onboard) or ground; null for low risk",
   "action": "maneuver, monitor or none", "decision_latency_min": "Minutes from screening to decision; null for low risk"}),
 "fct_maneuvers": ("Thruster burns.", "One row per maneuver", "maneuver_id", "executed_at", {
   "maneuver_id": "Maneuver key", "spacecraft_id": "Spacecraft key", "executed_at": "Burn time, UTC",
   "purpose": "collision_avoidance, station_keeping, formation_keeping or rpo_approach", "conjunction_id": "Conjunction it avoided (collision_avoidance only)",
   "autonomous": "Planned and executed onboard", "planned_dv_mps": "Planned delta-v, m/s", "executed_dv_mps": "Executed delta-v, m/s", "propellant_g": "Propellant used, g"}),
 "fct_nav_daily": ("Daily navigation health per spacecraft.", "One row per spacecraft per day", None, "nav_date", {
   "nav_date": "Day (UTC)", "spacecraft_id": "Spacecraft key", "firmware_version": "Firmware at end of day",
   "gnss_available_pct": "Share of the day with a GNSS fix", "jamming_minutes": "Minutes with GNSS jamming detected",
   "gnss_outage_minutes": "Minutes without a GNSS fix", "altpnt_minutes": "Minutes navigating on alt-PNT",
   "pos_error_p50_m": "Median position error vs. post-processed truth, m", "pos_error_p95_m": "95th percentile position error, m",
   "uptime_pct": "Share of the day in nominal mode (not safe mode)"}),
}
def table_entry(t):
    desc, grain, pk, tcol, cols = DOCS[t]
    types = dict(con.execute(f"SELECT column_name, column_type FROM (DESCRIBE {t})").fetchall())
    e = {}
    if tcol:
        mn, mx = con.execute(f"SELECT MIN({tcol})::DATE::VARCHAR, MAX({tcol})::DATE::VARCHAR FROM {t}").fetchone()
        e["date_range"] = {"column": tcol, "min": mn, "max": mx}
    e.update(name=t, file=f"{t}.parquet", description=desc, grain=grain)
    if pk: e["primary_key"] = pk
    e.update(rows=rows_of(t), bytes=size(t), columns=[{"name": c, "type": types[c], "description": cols[c]} for c in types])
    assert set(types) == set(cols), (t, set(types) ^ set(cols))
    return e

def test(table, name, sql_fail, warn_ok=False):
    n = q(sql_fail)
    return {"table": table, "test": name, "status": "pass" if n == 0 else "warn", "failing_rows": int(n)}
tests = [
 test("dim_spacecraft", "unique(spacecraft_id)", "SELECT COUNT(*)-COUNT(DISTINCT spacecraft_id) FROM dim_spacecraft"),
 test("dim_spacecraft", "relationships(customer_id -> dim_customers)", "SELECT COUNT(*) FROM dim_spacecraft WHERE customer_id NOT IN (SELECT customer_id FROM dim_customers)"),
 test("dim_rso", "unique(rso_id)", "SELECT COUNT(*)-COUNT(DISTINCT rso_id) FROM dim_rso"),
 test("fct_detections", "relationships(rso_id -> dim_rso)", "SELECT COUNT(*) FROM fct_detections WHERE rso_id IS NOT NULL AND rso_id NOT IN (SELECT rso_id FROM dim_rso)"),
 test("fct_detections", "rso_id is set only when matched", "SELECT COUNT(*) FROM fct_detections WHERE (rso_id IS NOT NULL) <> (match_status='matched')"),
 test("fct_conjunctions", "unique(conjunction_id)", "SELECT COUNT(*)-COUNT(DISTINCT conjunction_id) FROM fct_conjunctions"),
 test("fct_conjunctions", "tca > screened_at", "SELECT COUNT(*) FROM fct_conjunctions WHERE tca <= screened_at"),
 test("fct_conjunctions", "relationships(rso_id -> dim_rso)", "SELECT COUNT(*) FROM fct_conjunctions WHERE rso_id NOT IN (SELECT rso_id FROM dim_rso)"),
 test("fct_maneuvers", "collision_avoidance has conjunction_id", "SELECT COUNT(*) FROM fct_maneuvers WHERE (purpose='collision_avoidance') <> (conjunction_id IS NOT NULL)"),
 test("fct_maneuvers", "relationships(conjunction_id -> fct_conjunctions)", "SELECT COUNT(*) FROM fct_maneuvers WHERE conjunction_id IS NOT NULL AND conjunction_id NOT IN (SELECT conjunction_id FROM fct_conjunctions)"),
 test("fct_nav_daily", "unique(spacecraft_id, nav_date)", "SELECT COUNT(*)-COUNT(DISTINCT (spacecraft_id, nav_date)) FROM fct_nav_daily"),
 test("fct_detections", "detections on fragments before they were cataloged", "SELECT COUNT(*) FROM fct_detections d JOIN dim_rso r USING (rso_id) WHERE d.detected_at::DATE < r.first_cataloged"),
]

S = "orbit."
cat_metrics = [
 ("detections", "Onboard detections in a period.", f"SELECT COUNT(*) FROM {S}fct_detections WHERE detected_at::DATE BETWEEN DATE '2026-10-05' AND DATE '2026-10-11'", "week of 2026-10-05"),
 ("catalog_match_rate", "Matched detections / detections.", f"SELECT AVG((match_status='matched')::INT) FROM {S}fct_detections WHERE detected_at::DATE BETWEEN DATE '2026-10-05' AND DATE '2026-10-11'", "week of 2026-10-05"),
 ("false_alarm_rate", "False alarms / detections.", f"SELECT AVG((match_status='false_alarm')::INT) FROM {S}fct_detections WHERE detected_at::DATE BETWEEN DATE '2026-10-05' AND DATE '2026-10-11'", "week of 2026-10-05"),
 ("conjunctions", "Distinct conjunction_id screened (repeats removed).", f"SELECT COUNT(DISTINCT conjunction_id) FROM {S}fct_conjunctions WHERE screened_at::DATE BETWEEN DATE '2026-10-05' AND DATE '2026-10-11'", "week of 2026-10-05"),
 ("autonomous_decision_share", "Autonomous decisions / medium and high risk conjunctions (repeats removed).", f"SELECT AVG((decision_mode='autonomous')::INT) FROM (SELECT * FROM {S}fct_conjunctions QUALIFY ROW_NUMBER() OVER (PARTITION BY conjunction_id ORDER BY screened_at)=1) WHERE risk_tier<>'low' AND screened_at::DATE BETWEEN DATE '2026-10-05' AND DATE '2026-10-11'", "week of 2026-10-05"),
 ("delta_v_mps", "Executed delta-v, m/s.", f"SELECT SUM(executed_dv_mps) FROM {S}fct_maneuvers WHERE executed_at::DATE BETWEEN DATE '2026-01-01' AND DATE '2026-10-11'", "2026 to date"),
 ("nav_error_p95_m", "Mean of daily p95 position error across spacecraft-days, m.", f"SELECT AVG(pos_error_p95_m) FROM {S}fct_nav_daily WHERE nav_date BETWEEN DATE '2026-10-05' AND DATE '2026-10-11'", "week of 2026-10-05"),
]
con.execute("CREATE SCHEMA orbit")
for t in TABLES: con.execute(f"CREATE VIEW orbit.{t} AS SELECT * FROM main.{t}")
catalog = {
 "id": "orbit", "name": "Satellite autonomy ops",
 "story": "A 9-person spacecraft autonomy startup with 5 contracts; its onboard software and camera modules fly on 44 customer satellites, from a 4-cubesat swarm to GEO servicers. Onboard object detections, conjunctions, avoidance maneuvers and navigation health from Mar 2025 to Oct 2026. Fully synthetic.",
 "source": {"title": "Synthetic spacecraft autonomy operations data", "url": "https://github.com/vibedatascience/vibelogs/blob/main/residentquant/live/data/orbit/_generate.py",
            "license": "CC0", "credit": "ResidentQuant (generated)"},
 "tables": [table_entry(t) for t in TABLES], "tests": tests,
 "metrics": [{"name": n, "description": d, "sql": s, "value": round(float(q(s)), 6), "value_label": lbl} for n, d, s, lbl in cat_metrics],
 "caveats": [
  "Fully synthetic. Modeled on what spacecraft autonomy companies describe in public; customers, spacecraft and objects are invented.",
  "fct_conjunctions has repeated rows: the ground CDM feed resends messages. Count DISTINCT conjunction_id, or keep the first row per conjunction_id.",
  "unmatched is not a false alarm: unmatched is a real object that is not in the onboard catalog; false_alarm has no object behind it.",
  "The onboard catalog is uploaded weekly, so objects new to the public catalog show as unmatched for about a week.",
  "Spacecraft enter the data at data_start_date (later of commissioning and contract start), so the fleet grows over time. Normalize counts per spacecraft-day before comparing periods.",
  "nav_error_p95_m is the mean of daily per-spacecraft p95 values, not a fleet-wide p95.",
  "Firmware is per detection and per day; rollouts are staged by customer, so versions overlap for days.",
  "All times are UTC.",
 ],
 "questions": [
  "Why did the false alarm rate rise in the week of Oct 5, 2026?",
  "Why did conjunctions and delta-v jump in late August 2026?",
  "Does alt-PNT keep navigation error down during GNSS jamming? Compare missions.",
  "How much faster are autonomous avoidance decisions than ground decisions?",
  "Which firmware version has the best catalog match rate, by sensor?",
 ],
}
json.dump(catalog, open(f"{HERE}/catalog.json", "w"), indent=1)

# ---------------------------------------------------------------- semantic.json
def src(t, time, desc, dims):
    mn, mx = con.execute(f"SELECT MIN({time})::VARCHAR, MAX({time})::VARCHAR FROM {t}").fetchone()
    meas = [c for c, ty in con.execute(f"SELECT column_name, column_type FROM (DESCRIBE {t})").fetchall() if c not in dims and c != time]
    return {"kind": "aggregate", "file": f"{t}.parquet", "time": time, "description": desc, "rows": rows_of(t), "bytes": size(t),
            "date_min": mn, "date_max": mx, "dimensions": dims, "measures": meas}
sources = {
 "agg_detections_daily": src("agg_detections_daily", "detection_date", "Onboard detections by day, mission, sensor, firmware and sun angle. fct_detections is the source of truth.", {
   "customer_name": "Customer mission", "orbit_class": "SSO dawn-dusk, SSO midday, LEO 53 deg or GEO", "sensor": "HDR camera, ST-100 or ST-200 star tracker",
   "firmware_version": "Era-Core firmware", "sun_angle_band": "under 45 deg, 45 to 90 deg, 90 deg and over"}),
 "agg_conjunctions_daily": src("agg_conjunctions_daily", "screened_date", "Conjunctions by screening day, repeats removed (first row per conjunction_id).", {
   "customer_name": "Customer mission", "orbit_class": "Orbit class", "altitude_band": "under 525 km, 525 to 560 km, over 560 km, GEO",
   "risk_tier": "high, medium, low", "source": "onboard or ground_cdm", "decision_mode": "autonomous, ground or none (low risk)",
   "action": "maneuver, monitor, none", "object_type": "payload, payload_inactive, rocket_body, debris or breakup fragment"}),
 "agg_maneuvers_daily": src("agg_maneuvers_daily", "maneuver_date", "Thruster burns by day, mission and purpose.", {
   "customer_name": "Customer mission", "orbit_class": "Orbit class", "purpose": "collision_avoidance, station_keeping, formation_keeping, rpo_approach",
   "autonomous": "Planned and executed onboard"}),
 "agg_nav_daily": src("agg_nav_daily", "nav_date", "Navigation health by day and mission; one spacecraft-day per spacecraft per day.", {
   "customer_name": "Customer mission", "orbit_class": "Orbit class", "altpnt_enabled": "Alternative navigation turned on"}),
}
MET = [
 ("detections", "Detections", "number", "agg_detections_daily", "SUM(detections)", "Objects detected onboard.", "up"),
 ("catalog_match_rate", "Catalog match rate", "percent", "agg_detections_daily", "SUM(matched)/NULLIF(SUM(detections),0)", "Detections identified against the onboard catalog / detections.", "up"),
 ("false_alarm_rate", "False alarm rate", "percent", "agg_detections_daily", "SUM(false_alarms)/NULLIF(SUM(detections),0)", "Detections with no real object / detections.", "down"),
 ("unmatched_rate", "Unmatched rate", "percent", "agg_detections_daily", "SUM(unmatched)/NULLIF(SUM(detections),0)", "Real objects missing from the onboard catalog / detections.", "down"),
 ("onboard_latency_ms", "Onboard ID latency (ms)", "number", "agg_detections_daily", "SUM(latency_ms_sum)/NULLIF(SUM(detections),0)", "Average ms from image to identification.", "down"),
 ("conjunctions", "Conjunctions", "number", "agg_conjunctions_daily", "SUM(conjunctions)", "Close approaches screened, repeats removed.", "down"),
 ("high_risk_conjunctions", "High-risk conjunctions", "number", "agg_conjunctions_daily", "SUM(high_risk)", "Conjunctions with Pc >= 1e-4.", "down"),
 ("autonomous_decision_share", "Autonomous decision share", "percent", "agg_conjunctions_daily", "SUM(autonomous_decisions)/NULLIF(SUM(decisions),0)", "Medium and high risk conjunctions decided onboard / all medium and high risk.", "up"),
 ("decision_latency_min", "Decision latency (min)", "number", "agg_conjunctions_daily", "SUM(decision_latency_min_sum)/NULLIF(SUM(decisions),0)", "Average minutes from screening to decision.", "down"),
 ("maneuvers", "Maneuvers", "number", "agg_maneuvers_daily", "SUM(maneuvers)", "Thruster burns.", "down"),
 ("avoidance_maneuvers", "Avoidance maneuvers", "number", "agg_maneuvers_daily", "SUM(maneuvers) FILTER (WHERE purpose='collision_avoidance')", "Collision avoidance burns.", "down"),
 ("delta_v_mps", "Delta-v (m/s)", "number", "agg_maneuvers_daily", "SUM(delta_v_mps)", "Executed delta-v, m/s.", "down"),
 ("propellant_kg", "Propellant (kg)", "number", "agg_maneuvers_daily", "SUM(propellant_g)/1000", "Propellant used, kg.", "down"),
 ("dv_execution_error", "Delta-v execution error", "percent", "agg_maneuvers_daily", "SUM(dv_error_sum)/NULLIF(SUM(maneuvers),0)", "Average |executed - planned| / planned.", "down"),
 ("active_spacecraft", "Active spacecraft", "number", "agg_nav_daily", "SUM(spacecraft_days)/NULLIF(COUNT(DISTINCT nav_date),0)", "Average spacecraft operating per day.", "up"),
 ("jamming_minutes", "GNSS jamming minutes", "number", "agg_nav_daily", "SUM(jamming_minutes)", "Minutes with GNSS jamming detected, summed over spacecraft.", "down"),
 ("altpnt_hours", "Alt-PNT hours", "number", "agg_nav_daily", "SUM(altpnt_minutes)/60", "Hours navigating without GNSS on alt-PNT.", "up"),
 ("nav_error_p95_m", "Nav error p95 (m)", "number", "agg_nav_daily", "SUM(pos_error_p95_sum)/NULLIF(SUM(spacecraft_days),0)", "Mean daily p95 position error, m.", "down"),
 ("uptime", "Uptime", "percent", "agg_nav_daily", "SUM(uptime_sum)/NULLIF(SUM(spacecraft_days),0)", "Share of spacecraft-time in nominal mode.", "up"),
]
metrics = [{"name": n, "label": l, "format": f, "source": s, "sql": e, "description": d, "polarity": p,
            "value_all_time": round(float(q(f"SELECT {e} FROM {s}")), 4)} for n, l, f, s, e, d, p in MET]
recon = [
 ("detections", "SELECT SUM(detections) FROM agg_detections_daily", "SELECT COUNT(*) FROM fct_detections"),
 ("false_alarm_rate", "SELECT SUM(false_alarms)/SUM(detections) FROM agg_detections_daily", "SELECT AVG((match_status='false_alarm')::INT) FROM fct_detections"),
 ("conjunctions", "SELECT SUM(conjunctions) FROM agg_conjunctions_daily", "SELECT COUNT(DISTINCT conjunction_id) FROM fct_conjunctions"),
 ("delta_v_mps", "SELECT SUM(delta_v_mps) FROM agg_maneuvers_daily", "SELECT SUM(executed_dv_mps) FROM fct_maneuvers"),
 ("nav_error_p95_m", "SELECT SUM(pos_error_p95_sum)/SUM(spacecraft_days) FROM agg_nav_daily", "SELECT AVG(pos_error_p95_m) FROM fct_nav_daily"),
]
reconciliation = []
for m, a, b in recon:
    va, vb = round(float(q(a)), 4), round(float(q(b)), 4)
    reconciliation.append({"metric": m, "semantic": va, "raw": vb, "status": "pass" if abs(va - vb) < 1e-3 else "warn"})
semantic = {
 "id": "orbit", "as_of": AS_OF, "as_of_note": "Data ends Oct 11, 2026. The home page reviews complete weeks (Monday to Sunday).",
 "time_grains": ["day", "week", "month", "quarter", "year"], "sources": sources, "metrics": metrics,
 "home": {"grain": "week", "wbr": ["detections", "catalog_match_rate", "false_alarm_rate", "conjunctions", "autonomous_decision_share",
                                   "avoidance_maneuvers", "jamming_minutes", "nav_error_p95_m"],
          "segments": {"title": "Missions you own", "note": "by conjunctions in the week", "dimension": "customer_name",
                       "metric": "conjunctions", "extra": ["catalog_match_rate", "nav_error_p95_m"], "top": 6}},
 "reconciliation": reconciliation,
}
json.dump(semantic, open(f"{HERE}/semantic.json", "w"), indent=1)

total_rows = sum(rows_of(t) for t in TABLES)
total_bytes = sum(size(t) for t in TABLES)
print(json.dumps({"rows": {t: rows_of(t) for t in TABLES + AGGS}, "total_rows": total_rows, "total_bytes": total_bytes,
                  "tests": [(x["test"], x["status"], x["failing_rows"]) for x in tests], "recon": reconciliation}, indent=1, default=str))
