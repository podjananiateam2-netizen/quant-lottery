"""
Mobile Web App Backend - Jim Simons Quant Lottery Dashboard (Render-Ready)
Includes:
 1. 🎯 Tab 1: วันนี้แทงเลขอะไร
    - 🔥 สูตรเลข 2 ตัว: คัดมาแทงแค่ 4 ตลาดฟอร์มฮอต/วัน (Top 4 Hot Markets + สลับสูตร B วันที่ 3)
      (ทุน ~180-193฿/วัน | ความแม่น 48.7% (146/300 ไม้) | กำไร +3,091฿ (1x) / +4,001฿ (สลับ 1x↔2x) / +4,940฿ (อัดสูตร B 2x, ROI +34.1%))
    - 🎯 สูตรเลข 3 ตัวบน: 3D Cube Sniper (5×5×6 = 150 ตัว + สลับสูตร B วันที่ 3 อัตโนมัติ)
 2. ✅ Tab 2: ตรวจผล ถูก/ผิด & ประวัติกำไรรายวันครบทุกวัน (พร้อมโหมดเดินเงิน 1x / สลับ 1x↔2x / อัดสูตร B 2x)
 3. 📊 Tab 3: สถิติรวม & กราฟกำไรสะสม (Overall Stats & Analytics)
Author: Antigravity AI
"""
import os, sys, re, json, socket, time
from datetime import datetime, date, timedelta, timezone
from collections import Counter
from itertools import product
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ผลหวยหุ้น_ruay.txt")
_LAST_AUTO_SYNC_TS = 0.0

# บังคับใช้เวลาประเทศไทย (UTC+7) เสมอ แม้รันบนเซิร์ฟเวอร์ Render ที่เป็น UTC
THAI_TZ = timezone(timedelta(hours=7))

def get_thai_now():
    return datetime.now(THAI_TZ)

def get_thai_today():
    return get_thai_now().date()

def get_thai_today_str():
    return get_thai_today().strftime('%Y-%m-%d')

@app.after_request
def add_no_cache_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

PAY2 = 92
PAY3 = 850

# ==============================================================================
# 8 ตลาดตัวท็อปสำหรับสูตรเลข 2 ตัว (คัด 4 ตลาดฟอร์มฮอต/วัน + สลับสูตร B วันที่ 3)
# ==============================================================================
CANDIDATE_POOL_2D = [
    {
        'idx': 0,
        'title': 'หุ้นเกาหลี (เจาะล่าง 6×6)',
        'mkt': 'หุ้นเกาหลี',
        'display_name': '🇰🇷 หุ้นเกาหลี',
        'short_name': 'หุ้นเกาหลี',
        'draw_time': '13:00 น.',
        'a_target': 'BOT2', 'a_stype': 'GRID_DECAY', 'a_param': (6, 6), 'a_lb': 10, 'a_decay': 0.9, 'a_ro': 0,
        'switch_b': True,
        'b_name': 'B10: ย้ายฝั่งไปเจาะบน 6×6 Decay',
        'b_target': 'TOP2', 'b_stype': 'GRID_DECAY', 'b_param': (6, 6), 'b_lb': 10, 'b_decay': 0.9, 'b_ro': 0,
    },
    {
        'idx': 1,
        'title': 'นิเคอิเช้า (รูดบน 1 ตัว+ร้อย)',
        'mkt': 'นิเคอิรอบเช้า',
        'display_name': '🇯🇵 นิเคอิเช้า',
        'short_name': 'นิเคอิเช้า',
        'draw_time': '09:30 น.',
        'a_target': 'TOP2', 'a_stype': '19D_DECAY', 'a_param': (1, True), 'a_lb': 10, 'a_decay': 0.9, 'a_ro': 0,
        'switch_b': True,
        'b_name': 'B11: ย้ายฝั่งไปเจาะล่าง 6×6 โซนรอง (+2)',
        'b_target': 'BOT2', 'b_stype': 'GRID_DECAY', 'b_param': (6, 6), 'b_lb': 10, 'b_decay': 0.9, 'b_ro': 2,
    },
    {
        'idx': 2,
        'title': 'ฮั่งเส็งเช้า (รูดบน 2 ตัว+ไหล)',
        'mkt': 'ฮั่งเส็งรอบเช้า',
        'display_name': '🇭🇰 ฮั่งเส็งเช้า',
        'short_name': 'ฮั่งเส็งเช้า',
        'draw_time': '11:00 น.',
        'a_target': 'TOP2', 'a_stype': '19D_FLOW', 'a_param': 2, 'a_lb': 10, 'a_decay': 0.9, 'a_ro': 0,
        'switch_b': False,
        'b_name': 'A0: ยึดสูตร A เดิม (เด้งวันที่ 3 ดีอยู่แล้ว)',
        'b_target': 'TOP2', 'b_stype': '19D_FLOW', 'b_param': 2, 'b_lb': 10, 'b_decay': 0.9, 'b_ro': 0,
    },
    {
        'idx': 3,
        'title': 'นิเคอิบ่าย (รูดล่าง 2 ตัว+ร้อย)',
        'mkt': 'นิเคอิรอบบ่าย',
        'display_name': '🇯🇵 นิเคอิบ่าย',
        'short_name': 'นิเคอิบ่าย',
        'draw_time': '13:00 น.',
        'a_target': 'BOT2', 'a_stype': '19D_DECAY', 'a_param': (2, True), 'a_lb': 10, 'a_decay': 0.9, 'a_ro': 0,
        'switch_b': True,
        'b_name': 'B11: ย้ายฝั่งไปเจาะบน 6×6 โซนรอง (+2)',
        'b_target': 'TOP2', 'b_stype': 'GRID_DECAY', 'b_param': (6, 6), 'b_lb': 10, 'b_decay': 0.9, 'b_ro': 2,
    },
    {
        'idx': 4,
        'title': 'จีนบ่าย (เจาะล่าง 6×6 Count)',
        'mkt': 'จีนรอบบ่าย',
        'display_name': '🇨🇳 จีนบ่าย',
        'short_name': 'จีนบ่าย',
        'draw_time': '13:45 น.',
        'a_target': 'BOT2', 'a_stype': 'GRID_COUNT', 'a_param': (6, 6), 'a_lb': 10, 'a_decay': 0.9, 'a_ro': 0,
        'switch_b': True,
        'b_name': 'B11: ย้ายฝั่งไปเจาะบน 6×6 โซนรอง (+2)',
        'b_target': 'TOP2', 'b_stype': 'GRID_DECAY', 'b_param': (6, 6), 'b_lb': 10, 'b_decay': 0.9, 'b_ro': 2,
    },
    {
        'idx': 5,
        'title': 'หุ้นอียิปต์ (รูดบน 2 ตัว+ไหล)',
        'mkt': 'หุ้นอียิปต์',
        'display_name': '🇪🇬 หุ้นอียิปต์',
        'short_name': 'หุ้นอียิปต์',
        'draw_time': '20:00 น.',
        'a_target': 'TOP2', 'a_stype': '19D_FLOW', 'a_param': 2, 'a_lb': 10, 'a_decay': 0.9, 'a_ro': 0,
        'switch_b': True,
        'b_name': 'B9: ย้ายฝั่งไปรูดล่าง 2 ตัว+ไหล',
        'b_target': 'BOT2', 'b_stype': '19D_FLOW', 'b_param': 2, 'b_lb': 10, 'b_decay': 0.9, 'b_ro': 0,
    },
    {
        'idx': 6,
        'title': 'หุ้นอังกฤษ (เจาะบน 6×6)',
        'mkt': 'หุ้นอังกฤษ',
        'display_name': '🇬🇧 หุ้นอังกฤษ',
        'short_name': 'หุ้นอังกฤษ',
        'draw_time': '23:30 น.',
        'a_target': 'TOP2', 'a_stype': 'GRID_DECAY', 'a_param': (6, 6), 'a_lb': 10, 'a_decay': 0.9, 'a_ro': 0,
        'switch_b': True,
        'b_name': 'B11: ย้ายฝั่งไปเจาะล่าง 6×6 โซนรอง (+2)',
        'b_target': 'BOT2', 'b_stype': 'GRID_DECAY', 'b_param': (6, 6), 'b_lb': 10, 'b_decay': 0.9, 'b_ro': 2,
    },
    {
        'idx': 7,
        'title': 'หุ้นดาวโจนส์ (รูดล่าง 2 ตัว+ร้อย)',
        'mkt': 'หุ้นดาวโจนส์',
        'display_name': '🇺🇸 หุ้นดาวโจนส์',
        'short_name': 'หุ้นดาวโจนส์',
        'draw_time': '03:30 น.',
        'a_target': 'BOT2', 'a_stype': '19D_DECAY', 'a_param': (2, True), 'a_lb': 10, 'a_decay': 0.9, 'a_ro': 0,
        'switch_b': False,
        'b_name': 'A0: ยึดสูตร A เดิม (เด้งวันที่ 3 ดีอยู่แล้ว)',
        'b_target': 'BOT2', 'b_stype': '19D_DECAY', 'b_param': (2, True), 'b_lb': 10, 'b_decay': 0.9, 'b_ro': 0,
    },
]

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'

def load_all_lotteries():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    sections = re.split(r'\[\s*(.+?)\s*\]', content)
    lotteries = {}
    for i in range(1, len(sections), 2):
        name = sections[i].strip()
        body = sections[i+1].strip()
        lines = [l.strip() for l in body.split('\n') if l.strip()]
        records = {}
        for line in lines:
            m = re.match(r'วันที่\s*(\d{2}/\d{2}/\d{2})\s*->\s*3\s*ตัวบน:\s*(\d{3})\s*\|\s*2\s*ตัวล่าง:\s*(\d{2})', line)
            if m:
                d_raw, top3, bot2 = m.groups()
                day, month, year = d_raw.split('/')
                iso_date = f'20{year}-{month}-{day}'
                records[iso_date] = {
                    'top3': top3,
                    'h': int(top3[0]),
                    't': int(top3[1]),
                    'u': int(top3[2]),
                    'bot2': bot2,
                    'bt': int(bot2[0]),
                    'bu': int(bot2[1]),
                    'raw_date': f"{day}/{month}/{year}"
                }
        if records:
            lotteries[name] = records
    return lotteries

def save_all_lotteries(lotteries):
    lines = []
    for lot_name, data in lotteries.items():
        lines.append(f"[ {lot_name} ]")
        sorted_dates = sorted(data.keys(), reverse=True)
        for d in sorted_dates:
            item = data[d]
            dt = datetime.strptime(d, '%Y-%m-%d')
            raw_d = f"{dt.day:02d}/{dt.month:02d}/{str(dt.year)[-2:]}"
            lines.append(f"วันที่ {raw_d} -> 3 ตัวบน: {item['top3']} | 2 ตัวล่าง: {item['bot2']}")
        lines.append("")
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))

def sync_yahoo_finance():
    global _LAST_AUTO_SYNC_TS
    import urllib.request
    lotteries = load_all_lotteries()
    logs = []
    name_map = {
        'หุ้นเกาหลี': 'หุ้นเกาหลี',
        'หุ้นนิเคอิเช้า': 'นิเคอิรอบเช้า',
        'หุ้นนิเคอิบ่าย': 'นิเคอิรอบบ่าย',
        'ฮั่งเส็งเช้า': 'ฮั่งเส็งรอบเช้า',
        'ฮั่งเส็งบ่าย': 'ฮั่งเส็งรอบบ่าย',
        'จีนเช้า': 'จีนรอบเช้า',
        'จีนบ่าย': 'จีนรอบบ่าย',
        'ไต้หวัน': 'หุ้นไต้หวัน',
        'สิงคโปร์': 'หุ้นสิงคโปร์',
        'อียิปต์': 'หุ้นอียิปต์',
        'เยอรมัน': 'หุ้นเยอรมัน',
        'อังกฤษ': 'หุ้นอังกฤษ',
        'รัสเซีย': 'หุ้นรัสเซีย',
        'อินเดีย': 'หุ้นอินเดีย',
        'ดาวน์โจน': 'หุ้นดาวโจนส์',
        'มาเลย์': 'หวยมาเลย์',
        'ลาว': 'หวยลาว',
        'ลาว Super': 'หวยลาว Super',
        'ฮานอย': 'หวยเวียดนาม/ฮานอย',
        'ฮานอยพิเศษ': 'หวยเวียดนาม/ฮานอยพิเศษ',
        'ฮานอย VIP': 'หวยเวียดนาม/ฮานอย VIP',
    }
    added_count = 0
    updated_count = 0
    today_dt = get_thai_now()
    today_str = today_dt.strftime('%Y-%m-%d')
    ts_bust = int(time.time() * 1000)

    # ดึงเฉพาะวันนี้และเมื่อวานเสมอ (และดึงย้อนหลัง 2-6 วันเฉพาะวันที่ข้อมูลยังไม่ครบ) เพื่อให้ซิงค์ไวภายใน 1-2 วินาที
    date_list = []
    for i in range(7):
        d_dt = today_dt - timedelta(days=i)
        d_str = d_dt.strftime('%Y-%m-%d')
        if i <= 1:
            date_list.append(d_str)
        else:
            is_we = d_dt.weekday() in (5, 6)
            check_mkt = 'หวยเวียดนาม/ฮานอย VIP' if is_we else 'หุ้นอังกฤษ'
            if d_str not in lotteries.get(check_mkt, {}):
                date_list.append(d_str)

    def fetch_one_day(d_str):
        url = f"https://api66lotto.com/lotto/api/huay/prize?date={d_str}&_t={ts_bust}"
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
            }
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return d_str, json.loads(resp.read().decode('utf-8'))

    results_by_day = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(fetch_one_day, d_str): d_str for d_str in date_list}
        for fut in futures:
            d_str = futures[fut]
            try:
                results_by_day.append(fut.result())
            except Exception as e:
                logs.append(f"{d_str}: {str(e)}")

    # Process in chronological order
    for d_str, js in sorted(results_by_day, key=lambda x: x[0]):
        th_arr = js.get('thaiStock') or []
        if len(th_arr) >= 4:
            t3 = str(th_arr[3].get('topThree', '')).strip()
            b2 = str(th_arr[3].get('bottomTwo', '')).strip()
            if re.match(r'^\d{3}$', t3) and re.match(r'^\d{2}$', b2):
                d_dict = lotteries.setdefault('หุ้นไทยเย็น', {})
                if d_str not in d_dict:
                    added_count += 1
                elif d_dict[d_str]['top3'] != t3 or d_dict[d_str]['bot2'] != b2:
                    updated_count += 1
                d_dict[d_str] = {
                    'top3': t3, 'h': int(t3[0]), 't': int(t3[1]), 'u': int(t3[2]),
                    'bot2': b2, 'bt': int(b2[0]), 'bu': int(b2[1]),
                    'raw_date': f"{d_str.split('-')[2]}/{d_str.split('-')[1]}/{d_str.split('-')[0][-2:]}"
                }
        for item in (js.get('stock') or []):
            raw_name = (item.get('name') or '').strip()
            if raw_name in name_map:
                target_name = name_map[raw_name]
                t3 = str(item.get('topThree', '')).strip()
                b2 = str(item.get('bottomTwo', '')).strip()
                if re.match(r'^\d{3}$', t3) and re.match(r'^\d{2}$', b2):
                    save_d_str = (datetime.strptime(d_str, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d') if raw_name == 'ดาวน์โจน' else d_str
                    d_dict = lotteries.setdefault(target_name, {})
                    if save_d_str not in d_dict:
                        added_count += 1
                    elif d_dict[save_d_str]['top3'] != t3 or d_dict[save_d_str]['bot2'] != b2:
                        updated_count += 1
                    d_dict[save_d_str] = {
                        'top3': t3, 'h': int(t3[0]), 't': int(t3[1]), 'u': int(t3[2]),
                        'bot2': b2, 'bt': int(b2[0]), 'bu': int(b2[1]),
                        'raw_date': f"{save_d_str.split('-')[2]}/{save_d_str.split('-')[1]}/{save_d_str.split('-')[0][-2:]}"
                    }

    save_all_lotteries(lotteries)
    _LAST_AUTO_SYNC_TS = time.time()

    today_drawn_names = []
    for mkt_name, rec_map in lotteries.items():
        if today_str in rec_map:
            today_drawn_names.append(f"{mkt_name}({rec_map[today_str]['top3']}|{rec_map[today_str]['bot2']})")

    summary_msg = f"ซิงค์สำเร็จ (เวลาไทย {today_dt.strftime('%d/%m %H:%M น.')} | เพิ่มใหม่ {added_count}"
    if updated_count:
        summary_msg += f", อัปเดต {updated_count}"
    summary_msg += f" | วันนี้ออกแล้ว {len(today_drawn_names)} ตลาด)"
    logs.insert(0, summary_msg)
    return logs

def ensure_fresh_data():
    """Auto-syncs if data hasn't been synced in the last 3 minutes."""
    global _LAST_AUTO_SYNC_TS
    now_ts = time.time()
    if now_ts - _LAST_AUTO_SYNC_TS > 180:
        _LAST_AUTO_SYNC_TS = now_ts
        try:
            sync_yahoo_finance()
        except Exception:
            pass

# ==============================================================================
# 2D ENGINE: คัด 4 ตลาดฟอร์มฮอต/วัน (Top 4 Hot Markets + สลับสูตร B วันที่ 3)
# ==============================================================================
def get_19doors_list(digits):
    s = set()
    for d in digits:
        for i in range(10):
            s.add(f"{d}{i}")
            s.add(f"{i}{d}")
    return sorted(list(s))

def rank_digits_2d(history_2d, history_top3=None, decay=0.9, use_hundreds=False):
    scores = {str(d): 0.0 for d in range(10)}
    n = len(history_2d)
    for idx, val2 in enumerate(history_2d):
        w = decay ** (n - 1 - idx)
        d1, d2 = val2[0], val2[1]
        scores[d1] += w * 1.0
        scores[d2] += w * 1.0
        if d1 == d2:
            scores[d1] += w * 0.5
        if use_hundreds and history_top3 is not None:
            h = history_top3[idx][0]
            scores[h] += w * 0.6
    return [k for k, v in sorted(scores.items(), key=lambda x: (-x[1], x[0]))]

def rank_pos_2d(history_2d, decay=0.9):
    sc_t = {str(d): 0.0 for d in range(10)}
    sc_u = {str(d): 0.0 for d in range(10)}
    n = len(history_2d)
    for idx, val2 in enumerate(history_2d):
        w = decay ** (n - 1 - idx)
        sc_t[val2[0]] += w
        sc_u[val2[1]] += w
    rt = [k for k, v in sorted(sc_t.items(), key=lambda x: (-x[1], x[0]))]
    ru = [k for k, v in sorted(sc_u.items(), key=lambda x: (-x[1], x[0]))]
    return rt, ru

def compute_2d_signal_from_past(past_records, target, stype, param, decay=0.9, rank_offset=0):
    hist_2d = [p['top3'][1:] if target == 'TOP2' else p['bot2'] for p in past_records]
    hist_t3 = [p['top3'] for p in past_records]
    target_thai = '2 ตัวบน' if target == 'TOP2' else '2 ตัวล่าง'
    meta = {
        'target': target,
        'target_thai': target_thai,
        'stype': stype,
        'rank_offset': rank_offset,
        'root_digits': [],
        'tens': [],
        'units': [],
    }
    if stype == '19D_DECAY':
        k, use_h = param
        ranked = rank_digits_2d(hist_2d, hist_t3, decay=decay, use_hundreds=use_h)
        picks = ranked[rank_offset : rank_offset + k]
        nums = get_19doors_list(picks)
        meta['root_digits'] = picks
        meta['method_short'] = f"รูด 19 ประตู ({k} ตัว)"
        meta['detail_text'] = f"รูด 19 ประตู ({target_thai}) เลขเด่น: {', '.join(picks)}"
    elif stype == 'GRID_DECAY':
        nt, nu = param
        rt, ru = rank_pos_2d(hist_2d, decay=decay)
        pt = rt[rank_offset : rank_offset + nt]
        pu = ru[rank_offset : rank_offset + nu]
        nums = sorted([f"{t}{u}" for t, u in product(pt, pu)])
        meta['tens'] = pt
        meta['units'] = pu
        meta['method_short'] = f"เจาะ {nt}×{nu}"
        meta['detail_text'] = f"เจาะ {nt}×{nu} ({target_thai}) สิบ:[{','.join(pt)}] × หน่วย:[{','.join(pu)}]"
    elif stype == 'GRID_COUNT':
        nt, nu = param
        tsc = Counter([int(x[0]) for x in hist_2d])
        usc = Counter([int(x[1]) for x in hist_2d])
        rt = [str(x) for x, _ in tsc.most_common(10)]
        ru = [str(x) for x, _ in usc.most_common(10)]
        for dig in '0123456789':
            if dig not in rt: rt.append(dig)
            if dig not in ru: ru.append(dig)
        pt = rt[rank_offset : rank_offset + nt]
        pu = ru[rank_offset : rank_offset + nu]
        nums = sorted([f"{t}{u}" for t, u in product(pt, pu)])
        meta['tens'] = pt
        meta['units'] = pu
        meta['method_short'] = f"เจาะ {nt}×{nu} Count"
        meta['detail_text'] = f"เจาะ {nt}×{nu} ({target_thai}) สิบ:[{','.join(pt)}] × หน่วย:[{','.join(pu)}]"
    elif stype == '19D_FLOW':
        k = param
        sc = [0.0]*10
        for idx_p, p in enumerate(past_records):
            w = 0.9 ** (len(past_records) - 1 - idx_p)
            t_d, u_d, h_d = int(p['top3'][1]), int(p['top3'][2]), int(p['top3'][0])
            bt_d, bu_d = int(p['bot2'][0]), int(p['bot2'][1])
            if target == 'TOP2':
                sc[t_d] += w; sc[u_d] += w; sc[h_d] += w * 0.4
            else:
                sc[bt_d] += w; sc[bu_d] += w; sc[t_d] += w * 0.3; sc[u_d] += w * 0.3
        last_p = past_records[-1]
        if target == 'TOP2':
            sc[int(last_p['top3'][1])] += 1.2; sc[int(last_p['top3'][2])] += 1.2
        else:
            sc[int(last_p['bot2'][0])] += 1.0; sc[int(last_p['bot2'][1])] += 1.0
        ranked = [str(x) for x in sorted(range(10), key=lambda x: sc[x], reverse=True)]
        picks = ranked[rank_offset : rank_offset + k]
        nums = get_19doors_list(picks)
        meta['root_digits'] = picks
        meta['method_short'] = f"รูด 19 ประตู+ไหล ({k} ตัว)"
        meta['detail_text'] = f"รูด 19 ประตู+เลขไหล ({target_thai}) เลขเด่น: {', '.join(picks)}"
    meta['nums'] = nums
    meta['cost'] = len(nums)
    return meta

def build_2d_streams_and_portfolio(lotteries):
    """
    Builds the full chronological stream for all 8 candidate 2D markets
    (with Day-3 Formula B auto-switch) and simulates the Top-4 daily selection
    across all 75+ trading days, plus tracks live state for today/upcoming draws.
    """
    mkt_ab_stream = {}
    all_dates_set = set()

    for cfg in CANDIDATE_POOL_2D:
        title = cfg['title']
        mkt = cfg['mkt']
        v_dict = lotteries.get(mkt, {})
        dates = sorted(v_dict.keys())
        start_idx = 10
        stream = []
        d_map = {}
        st_a = 0
        for i in range(start_idx, len(dates)):
            d = dates[i]
            curr = v_dict[d]
            past_a = [v_dict[pd] for pd in dates[i - cfg['a_lb'] : i]]
            meta_a = compute_2d_signal_from_past(past_a, cfg['a_target'], cfg['a_stype'], cfg['a_param'], cfg['a_decay'], cfg['a_ro'])
            act_a = curr['top3'][1:] if cfg['a_target'] == 'TOP2' else curr['bot2']
            w_a = 1 if act_a in meta_a['nums'] else 0
            c_a = meta_a['cost']

            past_b = [v_dict[pd] for pd in dates[i - cfg['b_lb'] : i]]
            meta_b = compute_2d_signal_from_past(past_b, cfg['b_target'], cfg['b_stype'], cfg['b_param'], cfg['b_decay'], cfg['b_ro'])
            act_b = curr['top3'][1:] if cfg['b_target'] == 'TOP2' else curr['bot2']
            w_b = 1 if act_b in meta_b['nums'] else 0
            c_b = meta_b['cost']

            prev_st_a = st_a
            if st_a == 2 and cfg['switch_b']:
                rec = {
                    'date': d, 'cost': c_b, 'won': w_b, 'actual': act_b,
                    'top3': curr['top3'], 'bot2': curr['bot2'],
                    'tag': 'B_DAY3', 'prev_st_a': prev_st_a,
                    'active_meta': meta_b, 'alt_meta': meta_a,
                    'cfg': cfg
                }
                st_a = 0
            else:
                tag = 'A_DAY3' if st_a == 2 else 'A_NORM'
                rec = {
                    'date': d, 'cost': c_a, 'won': w_a, 'actual': act_a,
                    'top3': curr['top3'], 'bot2': curr['bot2'],
                    'tag': tag, 'prev_st_a': prev_st_a,
                    'active_meta': meta_a, 'alt_meta': meta_b,
                    'cfg': cfg
                }
                if w_a:
                    st_a = 0
                else:
                    st_a += 1
            stream.append(rec)
            d_map[d] = rec
            all_dates_set.add(d)
        mkt_ab_stream[title] = (stream, d_map, st_a)

    today_str_now = get_thai_today_str()
    valid_dates = sorted([
        d for d in all_dates_set
        if sum(1 for t in mkt_ab_stream if d in mkt_ab_stream[t][1]) >= 4
        and (d < today_str_now or sum(1 for t in mkt_ab_stream if d in mkt_ab_stream[t][1]) == len(CANDIDATE_POOL_2D))
    ])

    # Track multipliers for each staking mode across valid_dates
    mult_alt = {cfg['title']: 1 for cfg in CANDIDATE_POOL_2D}
    mult_boost = {cfg['title']: 1 for cfg in CANDIDATE_POOL_2D}
    mult_2x_hold = {cfg['title']: 1 for cfg in CANDIDATE_POOL_2D}

    daily_2d_map = {}

    for d in valid_dates:
        cands = []
        for cfg in CANDIDATE_POOL_2D:
            idx = cfg['idx']
            title = cfg['title']
            stream, d_map, _ = mkt_ab_stream[title]
            if d not in d_map:
                continue
            past = [x for x in stream if x['date'] < d]
            today_rec = d_map[d]
            today_tag = today_rec['tag']
            if len(past) < 3:
                score = 50.0 - idx
                hits5, len5, pnl5 = 0, len(past), 0
            else:
                last_w = past[-1]['won']
                ls = 0
                for x in reversed(past):
                    if not x['won']: ls += 1
                    else: break
                if ls >= 3:
                    continue
                w5 = past[-5:]
                pnl5 = sum((PAY2 - x['cost']) if x['won'] else -x['cost'] for x in w5)
                hits5 = sum(1 for x in w5 if x['won'])
                len5 = len(w5)
                score = (hits5 / len5) * 100.0 + pnl5 * 0.1 + (5.0 if last_w else 0.0)
                if today_tag in ('B_DAY3', 'A_DAY3'):
                    score += 20.0
            cands.append((score, -idx, title, hits5, len5, pnl5))

        cands.sort(reverse=True)
        chosen_info = cands[:4]
        backup_info = cands[4:]

        draws_list = []
        tot_cost_1x = 0; tot_pnl_1x = 0
        tot_cost_alt = 0; tot_pnl_alt = 0
        tot_cost_boost = 0; tot_pnl_boost = 0
        tot_cost_2x = 0; tot_pnl_2x = 0
        wins_count = 0

        for rank_no, (score, _, title, hits5, len5, pnl5) in enumerate(chosen_info, 1):
            rec = mkt_ab_stream[title][1][d]
            c = rec['cost']
            w = rec['won']
            tag = rec['tag']
            cfg = rec['cfg']

            m_1x = 1
            m_alt = mult_alt[title]
            mult_alt[title] = (2 if m_alt == 1 else 1) if w else 1

            m_boost = 2 if tag in ('B_DAY3', 'A_DAY3') else mult_boost[title]
            if tag in ('B_DAY3', 'A_DAY3'):
                mult_boost[title] = 1
            else:
                mult_boost[title] = (2 if m_boost == 1 else 1) if w else 1

            m_2x = mult_2x_hold[title]
            mult_2x_hold[title] = 2 if w else 1

            base_net = (PAY2 - c) if w else -c
            pnl_1x = base_net * m_1x
            pnl_alt = base_net * m_alt
            pnl_boost = base_net * m_boost
            pnl_2x = base_net * m_2x

            tot_cost_1x += c * m_1x; tot_pnl_1x += pnl_1x
            tot_cost_alt += c * m_alt; tot_pnl_alt += pnl_alt
            tot_cost_boost += c * m_boost; tot_pnl_boost += pnl_boost
            tot_cost_2x += c * m_2x; tot_pnl_2x += pnl_2x
            if w:
                wins_count += 1

            draws_list.append({
                'rank': rank_no,
                'score': round(score, 1),
                'hits5_str': f"{hits5}/{len5}",
                'pnl5': pnl5,
                'title': title,
                'market': cfg['mkt'],
                'name': cfg['display_name'],
                'short_name': cfg['short_name'],
                'draw_time': cfg['draw_time'],
                'tag': tag,
                'use_b': (tag == 'B_DAY3'),
                'formula_name': cfg['b_name'] if tag == 'B_DAY3' else f"สูตร A ({cfg['title'].split('(')[1][:-1]})",
                'target': rec['active_meta']['target'],
                'target_thai': rec['active_meta']['target_thai'],
                'method_short': rec['active_meta']['method_short'],
                'detail_text': rec['active_meta']['detail_text'],
                'root_digits': rec['active_meta']['root_digits'],
                'tens': rec['active_meta']['tens'],
                'units': rec['active_meta']['units'],
                'nums_count': c,
                'actual_top3': rec['top3'],
                'actual_bot2': rec['bot2'],
                'actual_target': rec['actual'],
                'hit': bool(w),
                'm_1x': m_1x, 'm_alt': m_alt, 'm_boost': m_boost, 'm_2x': m_2x,
                'cost_1x': c * m_1x, 'pnl_1x': pnl_1x,
                'cost_alt': c * m_alt, 'pnl_alt': pnl_alt,
                'cost_boost': c * m_boost, 'pnl_boost': pnl_boost,
                'cost_2x': c * m_2x, 'pnl_2x': pnl_2x,
            })

        # Stop-On-Win (SOW) on the 4 chosen markets sorted by draw time
        time_order = {'09:30 น.': 1, '11:00 น.': 2, '13:00 น.': 3, '13:45 น.': 4, '20:00 น.': 5, '23:30 น.': 6, '03:30 น.': 7}
        draws_by_time = sorted(draws_list, key=lambda x: (time_order.get(x['draw_time'], 99), x['rank']))
        sow_cost_1x, sow_pnl_1x = 0, 0
        sow_cost_2x, sow_pnl_2x = 0, 0
        for dr in draws_by_time:
            sow_cost_1x += dr['cost_1x']
            sow_pnl_1x += dr['pnl_1x']
            sow_cost_2x += dr['cost_boost']
            sow_pnl_2x += dr['pnl_boost']
            if dr['hit']:
                break

        daily_2d_map[d] = {
            'date': d,
            'draws': draws_list,
            'draws_count': len(draws_list),
            'wins_count': wins_count,
            'any_b': any(dr['use_b'] for dr in draws_list),
            'cost_1x': tot_cost_1x, 'pnl_1x': tot_pnl_1x,
            'cost_alt': tot_cost_alt, 'pnl_alt': tot_pnl_alt,
            'cost_boost': tot_cost_boost, 'pnl_boost': tot_pnl_boost,
            'cost_2x': tot_cost_2x, 'pnl_2x': tot_pnl_2x,
            'sow_cost_1x': sow_cost_1x, 'sow_pnl_1x': sow_pnl_1x,
            'sow_cost_2x': sow_cost_2x, 'sow_pnl_2x': sow_pnl_2x,
        }

    return mkt_ab_stream, valid_dates, daily_2d_map, mult_alt, mult_boost, mult_2x_hold

def get_2d_picks_for_date(target_date_str, lotteries, mkt_ab_stream, mult_alt_live, mult_boost_live):
    """
    Computes the Top 4 Hot Markets (+ 4 Backup Markets) for target_date_str.
    Works both for historical dates and live/today dates before draws occur.
    """
    cands = []
    for cfg in CANDIDATE_POOL_2D:
        idx = cfg['idx']
        title = cfg['title']
        mkt = cfg['mkt']
        v_dict = lotteries.get(mkt, {})
        dates_before = sorted([d for d in v_dict.keys() if d < target_date_str])
        if len(dates_before) < 10:
            continue

        stream, d_map, _ = mkt_ab_stream[title]
        past = [x for x in stream if x['date'] < target_date_str]

        # Determine Formula A streak entering target_date_str from past stream
        if target_date_str in d_map:
            prev_st_a = d_map[target_date_str]['prev_st_a']
            today_tag = d_map[target_date_str]['tag']
            meta_active = d_map[target_date_str]['active_meta']
            meta_alt = d_map[target_date_str]['alt_meta']
        else:
            # Compute st_a after all past draws < target_date_str
            st_a = 0
            for x in past:
                if x['tag'] == 'B_DAY3':
                    st_a = 0
                else:
                    # Need whether Formula A won on that past date
                    if x['won']:
                        st_a = 0
                    else:
                        st_a += 1
            prev_st_a = st_a
            past_a = [v_dict[pd] for pd in dates_before[-cfg['a_lb']:]]
            meta_a = compute_2d_signal_from_past(past_a, cfg['a_target'], cfg['a_stype'], cfg['a_param'], cfg['a_decay'], cfg['a_ro'])
            past_b = [v_dict[pd] for pd in dates_before[-cfg['b_lb']:]]
            meta_b = compute_2d_signal_from_past(past_b, cfg['b_target'], cfg['b_stype'], cfg['b_param'], cfg['b_decay'], cfg['b_ro'])
            if st_a == 2 and cfg['switch_b']:
                today_tag = 'B_DAY3'
                meta_active, meta_alt = meta_b, meta_a
            else:
                today_tag = 'A_DAY3' if st_a == 2 else 'A_NORM'
                meta_active, meta_alt = meta_a, meta_b

        # Score calculation (strictly from past < target_date_str)
        ls = 0
        for x in reversed(past):
            if not x['won']: ls += 1
            else: break
        skipped_by_ls = (len(past) >= 3 and ls >= 3)

        if len(past) < 3:
            score = 50.0 - idx
            hits5, len5, pnl5 = 0, len(past), 0
        else:
            last_w = past[-1]['won']
            w5 = past[-5:]
            pnl5 = sum((PAY2 - x['cost']) if x['won'] else -x['cost'] for x in w5)
            hits5 = sum(1 for x in w5 if x['won'])
            len5 = len(w5)
            score = (hits5 / len5) * 100.0 + pnl5 * 0.1 + (5.0 if last_w else 0.0)
            if today_tag in ('B_DAY3', 'A_DAY3'):
                score += 20.0
            if skipped_by_ls:
                score -= 500.0

        # Multiplier entering target_date_str
        m_alt = 1
        m_boost = 1
        for x in past:
            w = x['won']
            tg = x['tag']
            m_alt = (2 if m_alt == 1 else 1) if w else 1
            if tg in ('B_DAY3', 'A_DAY3'):
                m_boost = 1
            else:
                cur_mb = m_boost
                m_boost = (2 if cur_mb == 1 else 1) if w else 1
        if today_tag in ('B_DAY3', 'A_DAY3'):
            m_boost = 2

        actual_item = v_dict.get(target_date_str)
        actual_top3 = actual_item['top3'] if actual_item else None
        actual_bot2 = actual_item['bot2'] if actual_item else None
        actual_target = (actual_top3[1:] if meta_active['target'] == 'TOP2' else actual_bot2) if actual_item else None
        hit = (actual_target in meta_active['nums']) if actual_target else None

        cands.append({
            'score': round(score, 1),
            'sort_key': (score, -idx),
            'skipped_by_ls': skipped_by_ls,
            'lose_streak': ls,
            'prev_st_a': prev_st_a,
            'hits5_str': f"{hits5}/{len5}",
            'pnl5': pnl5,
            'title': title,
            'lottery_key': mkt,
            'name': cfg['display_name'],
            'short_name': cfg['short_name'],
            'draw_time': cfg['draw_time'],
            'tag': today_tag,
            'use_formula_b': (today_tag == 'B_DAY3'),
            'formula_label': f"🔄 สูตร B วันที่ 3 ({cfg['b_name']})" if today_tag == 'B_DAY3' else f"🟢 สูตร A ({cfg['title'].split('(')[1][:-1]})",
            'target': meta_active['target'],
            'target_thai': meta_active['target_thai'],
            'stype': meta_active['stype'],
            'method_short': meta_active['method_short'],
            'detail_text': meta_active['detail_text'],
            'root_digits': meta_active['root_digits'],
            'tens': meta_active['tens'],
            'units': meta_active['units'],
            'nums_count': meta_active['cost'],
            'nums_comma': ",".join(meta_active['nums']),
            'nums_space': " ".join(meta_active['nums']),
            'alt_target_thai': meta_alt['target_thai'],
            'alt_detail_text': meta_alt['detail_text'],
            'alt_nums_count': meta_alt['cost'],
            'alt_nums_comma': ",".join(meta_alt['nums']),
            'm_alt': m_alt,
            'm_boost': m_boost,
            'cost_1x': meta_active['cost'],
            'cost_alt': meta_active['cost'] * m_alt,
            'cost_boost': meta_active['cost'] * m_boost,
            'actual_top3': actual_top3,
            'actual_bot2': actual_bot2,
            'actual_target': actual_target,
            'hit': hit,
        })

    cands.sort(key=lambda x: x['sort_key'], reverse=True)
    for i, item in enumerate(cands, 1):
        item['rank'] = i
        item['is_top4'] = (i <= 4 and not item['skipped_by_ls'])
        del item['sort_key']

    top4 = [x for x in cands if x['is_top4']][:4]
    backups = [x for x in cands if x not in top4]
    return top4, backups

# ==============================================================================
# 3D ENGINE: 3D Cube Sniper (5×5×6 = 150 ตัว + สลับสูตร B วันที่ 3)
# ==============================================================================
def compute_market_models(key_name, d_str, is_we, hsi_today, sorted_lots, date_wd):
    hist = sorted_lots.get(key_name, [])
    past = [item for item in hist if item[0] < d_str]
    if len(past) < 12:
        return None

    prev_dji = None
    prev_ftse = None
    if not is_we and key_name == 'ฮั่งเส็งรอบเช้า':
        dji_past = [item for item in sorted_lots.get('หุ้นดาวโจนส์', []) if item[0] < d_str]
        ftse_past = [item for item in sorted_lots.get('หุ้นอังกฤษ', []) if item[0] < d_str]
        if dji_past: prev_dji = dji_past[-1][1]
        if ftse_past: prev_ftse = ftse_past[-1][1]

    # --- 1. 3D Formula A (Normal Regime) ---
    recent_a = past[-20:]
    ha_sc = [0.0]*10; ta_sc = [0.0]*10; ua_sc = [0.0]*10
    for _, it in recent_a:
        ha_sc[it['h']] += 1.0; ta_sc[it['t']] += 1.0; ua_sc[it['u']] += 1.0
    if not is_we and key_name == 'ฮั่งเส็งรอบเช้า':
        if prev_dji:
            ha_sc[prev_dji['h']] -= 1.0; ta_sc[prev_dji['t']] -= 1.0; ua_sc[prev_dji['u']] -= 1.0
        if prev_ftse:
            ha_sc[prev_ftse['h']] += 0.5; ta_sc[prev_ftse['t']] += 0.5; ua_sc[prev_ftse['u']] += 0.5
    elif not is_we and key_name in ('หุ้นอังกฤษ', 'หุ้นดาวโจนส์') and hsi_today:
        ha_sc[hsi_today['h']] += 1.5; ta_sc[hsi_today['t']] += 1.5; ua_sc[hsi_today['u']] += 1.5
        ha_sc[hsi_today['t']] += 1.0; ta_sc[hsi_today['u']] += 1.0; ua_sc[hsi_today['h']] += 1.0
    elif is_we:
        for p_date, it in recent_a[-6:]:
            if date_wd.get(p_date, datetime.strptime(p_date, '%Y-%m-%d').weekday()) in (3, 4):
                ha_sc[it['h']] += 1.2; ta_sc[it['t']] += 1.2; ua_sc[it['u']] += 1.2

    ha_ord = sorted(range(10), key=lambda x: ha_sc[x], reverse=True)
    ta_ord = sorted(range(10), key=lambda x: ta_sc[x], reverse=True)
    ua_ord = sorted(range(10), key=lambda x: ua_sc[x], reverse=True)
    if is_we:
        ha_top, ta_top, ua_top = ha_ord[0:4], ta_ord[0:3], ua_ord[0:10]
    else:
        ha_top, ta_top, ua_top = ha_ord[0:5], ta_ord[0:5], ua_ord[0:6]

    # --- 2. 3D Formula B (Day-3 Recovery Mid-Cool Rotation) ---
    recent_b = past[-7:]
    hb_sc = [0.0]*10; tb_sc = [0.0]*10; ub_sc = [0.0]*10
    n_b = len(recent_b)
    for idx, (_, it) in enumerate(recent_b):
        w = 0.85 ** (n_b - 1 - idx)
        hb_sc[it['h']] += w; tb_sc[it['t']] += w; ub_sc[it['u']] += w
    if not is_we and key_name == 'ฮั่งเส็งรอบเช้า':
        if prev_dji:
            hb_sc[prev_dji['h']] -= 1.0; tb_sc[prev_dji['t']] -= 1.0; ub_sc[prev_dji['u']] -= 1.0
        if prev_ftse:
            hb_sc[prev_ftse['h']] += 0.5; tb_sc[prev_ftse['t']] += 0.5; ub_sc[prev_ftse['u']] += 0.5
    elif not is_we and key_name in ('หุ้นอังกฤษ', 'หุ้นดาวโจนส์') and hsi_today:
        hb_sc[hsi_today['h']] += 1.5; tb_sc[hsi_today['t']] += 1.5; ub_sc[hsi_today['u']] += 1.5
        hb_sc[hsi_today['t']] += 2.0; tb_sc[hsi_today['u']] += 2.0; ub_sc[hsi_today['h']] += 2.0
    elif is_we:
        for p_date, it in recent_b[-6:]:
            if date_wd.get(p_date, datetime.strptime(p_date, '%Y-%m-%d').weekday()) in (3, 4):
                hb_sc[it['h']] += 1.2; tb_sc[it['t']] += 1.2; ub_sc[it['u']] += 1.2

    hb_ord = sorted(range(10), key=lambda x: hb_sc[x], reverse=True)
    tb_ord = sorted(range(10), key=lambda x: tb_sc[x], reverse=True)
    ub_ord = sorted(range(10), key=lambda x: ub_sc[x], reverse=True)
    hb_top, tb_top, ub_top = hb_ord[3:8], tb_ord[3:8], ub_ord[2:8]

    return {
        'a': {'h': ha_top, 't': ta_top, 'u': ua_top, 'bet': len(ha_top)*len(ta_top)*len(ua_top)},
        'b': {'h': hb_top, 't': tb_top, 'u': ub_top, 'bet': len(hb_top)*len(tb_top)*len(ub_top)},
    }

def get_regime_state_by_date(lotteries, sorted_lots, date_wd, all_dates_sorted):
    weekday_keys = ['ฮั่งเส็งรอบเช้า', 'หุ้นอังกฤษ', 'หุ้นดาวโจนส์']
    weekend_keys = ['หวยเวียดนาม/ฮานอยพิเศษ', 'หวยเวียดนาม/ฮานอย', 'หวยลาว Super', 'หวยเวียดนาม/ฮานอย VIP']
    
    cur_st = 0
    state_map = {}
    for d_str in all_dates_sorted:
        wd = date_wd[d_str]
        is_we = wd in (5, 6)
        targets = weekend_keys if is_we else weekday_keys
        hsi_today = lotteries.get('ฮั่งเส็งรอบเช้า', {}).get(d_str)
        
        use_b = (cur_st == 2) and (not is_we)
        day_has_draws = False
        day_hit = False
        drawn_count = 0
        
        for k in targets:
            lot_data = lotteries.get(k, {})
            if d_str not in lot_data:
                continue
            m = compute_market_models(k, d_str, is_we, hsi_today, sorted_lots, date_wd)
            if not m:
                continue
            day_has_draws = True
            drawn_count += 1
            act = lot_data[d_str]
            active_3d = m['b'] if use_b else m['a']
            if (act['h'] in active_3d['h']) and (act['t'] in active_3d['t']) and (act['u'] in active_3d['u']):
                day_hit = True
                
        if day_has_draws:
            state_map[d_str] = {
                'use_b': use_b,
                'prev_lose_streak': cur_st,
                'is_complete': drawn_count == len(targets) or d_str < all_dates_sorted[-1]
            }
            if not is_we:
                if day_hit:
                    cur_st = 0
                elif state_map[d_str]['is_complete']:
                    if use_b:
                        cur_st = 0
                    else:
                        cur_st += 1
    return state_map, cur_st

def get_today_drawn_summary(lotteries, target_date_str):
    order_list = [
        ('นิเคอิรอบเช้า', '🇯🇵 นิเคอิเช้า', '09:30'),
        ('จีนรอบเช้า', '🇨🇳 จีนเช้า', '10:30'),
        ('ฮั่งเส็งรอบเช้า', '🇭🇰 ฮั่งเส็งเช้า', '11:00'),
        ('หุ้นไต้หวัน', '🇹🇼 ไต้หวัน', '12:15'),
        ('หุ้นเกาหลี', '🇰🇷 เกาหลี', '13:00'),
        ('นิเคอิรอบบ่าย', '🇯🇵 นิเคอิบ่าย', '13:00'),
        ('จีนรอบบ่าย', '🇨🇳 จีนบ่าย', '13:45'),
        ('ฮั่งเส็งรอบบ่าย', '🇭🇰 ฮั่งเส็งบ่าย', '15:00'),
        ('หุ้นสิงคโปร์', '🇸🇬 สิงคโปร์', '16:15'),
        ('หุ้นไทยเย็น', '🇹🇭 ไทยเย็น', '16:30'),
        ('หุ้นอินเดีย', '🇮🇳 อินเดีย', '17:00'),
        ('หวยเวียดนาม/ฮานอยพิเศษ', '🇻🇳 ฮานอยพิเศษ', '17:30'),
        ('หวยเวียดนาม/ฮานอย', '🇻🇳 ฮานอยปกติ', '18:30'),
        ('หวยลาว Super', '🇱🇦 ลาว Super', '19:00'),
        ('หวยเวียดนาม/ฮานอย VIP', '🇻🇳 ฮานอย VIP', '19:30'),
        ('หุ้นอียิปต์', '🇪🇬 อียิปต์', '20:00'),
        ('หวยลาว', '🇱🇦 ลาวพัฒนา', '20:30'),
        ('หุ้นรัสเซีย', '🇷🇺 รัสเซีย', '22:45'),
        ('หุ้นเยอรมัน', '🇩🇪 เยอรมัน', '23:00'),
        ('หุ้นอังกฤษ', '🇬🇧 อังกฤษ', '23:30'),
        ('หุ้นดาวโจนส์', '🇺🇸 ดาวโจนส์', '03:30'),
    ]
    out = []
    for k, label, tm in order_list:
        rec = lotteries.get(k, {}).get(target_date_str)
        if rec:
            out.append({
                'key': k,
                'label': label,
                'time': tm,
                'top3': rec['top3'],
                'bot2': rec['bot2']
            })
    return out

def calculate_picks(target_date_str=None):
    ensure_fresh_data()
    lotteries = load_all_lotteries()
    all_dates = set()
    for lot_dict in lotteries.values():
        all_dates.update(lot_dict.keys())
    all_dates_sorted = sorted(list(all_dates))
    date_wd = {d: datetime.strptime(d, '%Y-%m-%d').weekday() for d in all_dates_sorted}
    sorted_lots = {k: sorted(v.items(), key=lambda x: x[0]) for k, v in lotteries.items()}
    
    state_map, latest_streak = get_regime_state_by_date(lotteries, sorted_lots, date_wd, all_dates_sorted)
    mkt_ab_stream, _, _, mult_alt_live, mult_boost_live, _ = build_2d_streams_and_portfolio(lotteries)

    if not target_date_str:
        target_dt = get_thai_today()
        target_date_str = target_dt.strftime('%Y-%m-%d')
    else:
        target_dt = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        
    is_weekend = target_dt.weekday() in [5, 6]
    date_wd[target_date_str] = target_dt.weekday()
    
    if target_date_str in state_map:
        use_formula_b = state_map[target_date_str]['use_b']
        prev_streak = state_map[target_date_str]['prev_lose_streak']
    else:
        use_formula_b = (latest_streak == 2) and (not is_weekend)
        prev_streak = latest_streak

    # 1. Compute 2D Top 4 Hot Markets picks
    picks_2d_top4, picks_2d_backup = get_2d_picks_for_date(
        target_date_str, lotteries, mkt_ab_stream, mult_alt_live, mult_boost_live
    )

    # 2. Compute 3D Cube Sniper picks
    if not is_weekend:
        targets = [
            ('ฮั่งเส็งรอบเช้า', '🇭🇰 ฮั่งเส็งเช้า', '11:00 น.'),
            ('หุ้นอังกฤษ', '🇬🇧 หุ้นอังกฤษ', '23:30 น.'),
            ('หุ้นดาวโจนส์', '🇺🇸 หุ้นดาวโจนส์', '03:30 น.')
        ]
    else:
        targets = [
            ('หวยเวียดนาม/ฮานอยพิเศษ', '🇻🇳 ฮานอยพิเศษ', '17:30 น.'),
            ('หวยเวียดนาม/ฮานอย', '🇻🇳 ฮานอยปกติ', '18:30 น.'),
            ('หวยลาว Super', '🇱🇦 ลาว Super', '19:00 น.'),
            ('หวยเวียดนาม/ฮานอย VIP', '🇻🇳 ฮานอย VIP', '19:30 น.')
        ]
        
    hsi_today = lotteries.get('ฮั่งเส็งรอบเช้า', {}).get(target_date_str)
    picks_3d = []
    
    for key_name, display_name, draw_time in targets:
        m = compute_market_models(key_name, target_date_str, is_weekend, hsi_today, sorted_lots, date_wd)
        if not m:
            continue
            
        active_3d = m['b'] if use_formula_b else m['a']
        alt_3d = m['a'] if use_formula_b else m['b']
        
        nums_3d = [f"{h}{t}{u}" for h in active_3d['h'] for t in active_3d['t'] for u in active_3d['u']]
        nums_3d_alt = [f"{h}{t}{u}" for h in alt_3d['h'] for t in alt_3d['t'] for u in alt_3d['u']]
        
        actual_item = lotteries.get(key_name, {}).get(target_date_str)
        hit_3d = None
        if actual_item:
            hit_3d = (actual_item['h'] in active_3d['h']) and (actual_item['t'] in active_3d['t']) and (actual_item['u'] in active_3d['u'])
        
        picks_3d.append({
            'lottery_key': key_name,
            'name': display_name,
            'draw_time': draw_time,
            'use_formula_b': use_formula_b,
            'prev_lose_streak': prev_streak,
            'formula_label': '🔄 สูตร B (แก้ทางวันที่ 3: Mid-Cool 5×5×6)' if use_formula_b else ('🎯 สูตร A (4×3×10 วันหยุด)' if is_weekend else '🎯 สูตร A (Hot Top 5×5×6)'),
            'h_top': active_3d['h'],
            't_top': active_3d['t'],
            'u_top': active_3d['u'],
            'h_alt': alt_3d['h'],
            't_alt': alt_3d['t'],
            'u_alt': alt_3d['u'],
            'nums_3d_count': len(nums_3d),
            'nums_3d_comma': ",".join(nums_3d),
            'nums_3d_space': " ".join(nums_3d),
            'nums_3d_alt_count': len(nums_3d_alt),
            'nums_3d_alt_comma': ",".join(nums_3d_alt),
            'actual_top3': actual_item['top3'] if actual_item else None,
            'actual_bot2': actual_item['bot2'] if actual_item else None,
            'hit_3d': hit_3d,
        })

    today_drawn = get_today_drawn_summary(lotteries, target_date_str)
    return picks_3d, picks_2d_top4, picks_2d_backup, is_weekend, use_formula_b, prev_streak, today_drawn, target_date_str

def generate_history_data():
    ensure_fresh_data()
    lotteries = load_all_lotteries()
    today_str = get_thai_today_str()
    all_dates = set()
    for lot_dict in lotteries.values():
        all_dates.update(lot_dict.keys())
    all_dates.add(today_str)
    all_dates_sorted = sorted(list(all_dates))
    date_wd = {d: datetime.strptime(d, '%Y-%m-%d').weekday() for d in all_dates_sorted}
    sorted_lots = {k: sorted(v.items(), key=lambda x: x[0]) for k, v in lotteries.items()}
    
    state_map, latest_streak = get_regime_state_by_date(lotteries, sorted_lots, date_wd, all_dates_sorted)
    mkt_ab_stream, valid_2d_dates, daily_2d_map, mult_alt_live, mult_boost_live, _ = build_2d_streams_and_portfolio(lotteries)

    chrono_days = []
    # แยกตัวคูณเดินเงิน 3D ระหว่าง วันจันทร์-ศุกร์ (wd_mult) และ วันเสาร์-อาทิตย์ (we_mult) ออกจากกัน 100%
    wd_mult = {'all': 1, 'sow': 1, 'alt': 1, 'exp': 1}
    we_mult = {'all': 1, 'sow': 1, 'alt': 1, 'exp': 1}
    
    for d_str in all_dates_sorted:
        dt = datetime.strptime(d_str, '%Y-%m-%d')
        is_weekend = dt.weekday() in [5, 6]
        is_live_today = (d_str == today_str)
        cur_m = we_mult if is_weekend else wd_mult

        if not is_weekend:
            targets = [
                ('ฮั่งเส็งรอบเช้า', '🇭🇰 ฮั่งเส็งเช้า', '11:00 น.'),
                ('หุ้นอังกฤษ', '🇬🇧 หุ้นอังกฤษ', '23:30 น.'),
                ('หุ้นดาวโจนส์', '🇺🇸 หุ้นดาวโจนส์', '03:30 น.')
            ]
        else:
            targets = [
                ('หวยเวียดนาม/ฮานอยพิเศษ', '🇻🇳 ฮานอยพิเศษ', '17:30 น.'),
                ('หวยเวียดนาม/ฮานอย', '🇻🇳 ฮานอยปกติ', '18:30 น.'),
                ('หวยลาว Super', '🇱🇦 ลาว Super', '19:00 น.'),
                ('หวยเวียดนาม/ฮานอย VIP', '🇻🇳 ฮานอย VIP', '19:30 น.')
            ]
            
        hsi_today = lotteries.get('ฮั่งเส็งรอบเช้า', {}).get(d_str)
        if d_str in state_map:
            use_b_3d = state_map[d_str]['use_b']
            prev_st_3d = state_map[d_str]['prev_lose_streak']
        else:
            use_b_3d = (latest_streak == 2) and (not is_weekend)
            prev_st_3d = latest_streak
        
        day_draws_3d = []
        total_bets_3d = 0
        total_payout_3d = 0
        drawn_3d_count = 0
        
        for key_name, display_name, draw_time in targets:
            lot_data = lotteries.get(key_name, {})
            m = compute_market_models(key_name, d_str, is_weekend, hsi_today, sorted_lots, date_wd)
            if not m:
                continue
            active_3d = m['b'] if use_b_3d else m['a']
            bet_3d = active_3d['bet']

            if d_str in lot_data:
                actual = lot_data[d_str]
                actual_top3 = actual['top3']
                actual_2d = f"{actual['t']}{actual['u']}"
                hit_3d = (actual['h'] in active_3d['h']) and (actual['t'] in active_3d['t']) and (actual['u'] in active_3d['u'])
                payout_3d = 850 if hit_3d else 0
                total_bets_3d += bet_3d
                total_payout_3d += payout_3d
                drawn_3d_count += 1
                day_draws_3d.append({
                    'market': key_name,
                    'name': display_name,
                    'draw_time': draw_time,
                    'actual_top3': actual_top3,
                    'actual_bot2': actual['bot2'],
                    'actual_2d': actual_2d,
                    'hit_3d': hit_3d,
                    'bet_3d': bet_3d,
                    'payout_3d': payout_3d,
                    'use_b': use_b_3d,
                    'is_pending': False
                })
            elif is_live_today:
                day_draws_3d.append({
                    'market': key_name,
                    'name': display_name,
                    'draw_time': draw_time,
                    'actual_top3': None,
                    'actual_bot2': None,
                    'actual_2d': None,
                    'hit_3d': None,
                    'bet_3d': bet_3d,
                    'payout_3d': 0,
                    'use_b': use_b_3d,
                    'is_pending': True
                })

        day_2d_info = daily_2d_map.get(d_str)
        backup_2d_drawn = []

        if is_live_today and not is_weekend and not day_2d_info:
            top4_today, backup_today = get_2d_picks_for_date(d_str, lotteries, mkt_ab_stream, mult_alt_live, mult_boost_live)
            live_draws_2d = []
            tot_c_1x = 0; tot_p_1x = 0
            tot_c_alt = 0; tot_p_alt = 0
            tot_c_boost = 0; tot_p_boost = 0
            tot_c_2x = 0; tot_p_2x = 0
            w_cnt = 0
            drawn_2d_cnt = 0
            for it in top4_today:
                c = it['nums_count']
                m_1x = 1
                m_alt = it['m_alt']
                m_boost = it['m_boost']
                m_2x = it['m_alt']
                if it['actual_top3'] is not None:
                    drawn_2d_cnt += 1
                    w = 1 if it['hit'] else 0
                    if w: w_cnt += 1
                    base_net = (PAY2 - c) if w else -c
                    p_1x = base_net * m_1x
                    p_alt = base_net * m_alt
                    p_boost = base_net * m_boost
                    p_2x = base_net * m_2x
                    tot_c_1x += c * m_1x; tot_p_1x += p_1x
                    tot_c_alt += c * m_alt; tot_p_alt += p_alt
                    tot_c_boost += c * m_boost; tot_p_boost += p_boost
                    tot_c_2x += c * m_2x; tot_p_2x += p_2x
                    is_pend = False
                else:
                    p_1x = 0; p_alt = 0; p_boost = 0; p_2x = 0
                    is_pend = True

                live_draws_2d.append({
                    'rank': it['rank'],
                    'score': it['score'],
                    'hits5_str': it['hits5_str'],
                    'pnl5': it['pnl5'],
                    'title': it['title'],
                    'market': it['lottery_key'],
                    'name': it['name'],
                    'short_name': it['short_name'],
                    'draw_time': it['draw_time'],
                    'tag': it['tag'],
                    'use_b': it['use_formula_b'],
                    'formula_name': it['formula_label'],
                    'target': it['target'],
                    'target_thai': it['target_thai'],
                    'method_short': it['method_short'],
                    'detail_text': it['detail_text'],
                    'root_digits': it['root_digits'],
                    'tens': it['tens'],
                    'units': it['units'],
                    'nums_count': c,
                    'actual_top3': it['actual_top3'],
                    'actual_bot2': it['actual_bot2'],
                    'actual_target': it['actual_target'],
                    'hit': it['hit'],
                    'is_pending': is_pend,
                    'm_1x': m_1x, 'm_alt': m_alt, 'm_boost': m_boost, 'm_2x': m_2x,
                    'cost_1x': c * m_1x if not is_pend else 0, 'pnl_1x': p_1x,
                    'cost_alt': c * m_alt if not is_pend else 0, 'pnl_alt': p_alt,
                    'cost_boost': c * m_boost if not is_pend else 0, 'pnl_boost': p_boost,
                    'cost_2x': c * m_2x if not is_pend else 0, 'pnl_2x': p_2x,
                })
            for bk in backup_today:
                if bk['actual_top3'] is not None:
                    backup_2d_drawn.append({
                        'rank': bk['rank'],
                        'name': bk['name'],
                        'draw_time': bk['draw_time'],
                        'method_short': bk['method_short'],
                        'target_thai': bk['target_thai'],
                        'actual_top3': bk['actual_top3'],
                        'actual_bot2': bk['actual_bot2'],
                        'hit': bk['hit'],
                        'use_b': bk['use_formula_b'],
                    })
            day_2d_info = {
                'date': d_str,
                'draws': live_draws_2d,
                'draws_count': drawn_2d_cnt,
                'planned_count': len(live_draws_2d),
                'wins_count': w_cnt,
                'any_b': any(dr['use_b'] for dr in live_draws_2d),
                'cost_1x': tot_c_1x, 'pnl_1x': tot_p_1x,
                'cost_alt': tot_c_alt, 'pnl_alt': tot_p_alt,
                'cost_boost': tot_c_boost, 'pnl_boost': tot_p_boost,
                'cost_2x': tot_c_2x, 'pnl_2x': tot_p_2x,
                'sow_cost_1x': tot_c_1x, 'sow_pnl_1x': tot_p_1x,
                'sow_cost_2x': tot_c_boost, 'sow_pnl_2x': tot_p_boost,
            }

        if not day_draws_3d and not day_2d_info:
            continue

        # 3D calculations (only across completed draws of the day)
        sow_bets_3d, sow_payout_3d = 0, 0
        for d in day_draws_3d:
            if d.get('is_pending'):
                continue
            sow_bets_3d += d['bet_3d']
            if d['hit_3d']:
                sow_payout_3d += d['payout_3d']
                break

        prof_3d_1x = total_payout_3d - total_bets_3d
        prof_3d_sow_1x = sow_payout_3d - sow_bets_3d
        prof_3d_2x = prof_3d_1x * cur_m['all']
        prof_3d_alt = prof_3d_1x * cur_m['alt']
        prof_3d_exp = prof_3d_1x * cur_m['exp']
        prof_3d_sow_2x = prof_3d_sow_1x * cur_m['sow']

        # 2D Top 4 Hot Markets calculations
        if day_2d_info:
            draws_2d = day_2d_info['draws']
            wins_2d = day_2d_info['wins_count']
            bets_2d_count = day_2d_info['draws_count']
            planned_2d_count = day_2d_info.get('planned_count', bets_2d_count)
            any_b_2d = day_2d_info['any_b']
            cost_2d_1x = day_2d_info['cost_1x']; prof_2d_1x = day_2d_info['pnl_1x']
            cost_2d_alt = day_2d_info['cost_alt']; prof_2d_alt = day_2d_info['pnl_alt']
            cost_2d_boost = day_2d_info['cost_boost']; prof_2d_boost = day_2d_info['pnl_boost']
            cost_2d_2x = day_2d_info['cost_2x']; prof_2d_2x = day_2d_info['pnl_2x']
            sow_cost_2d_1x = day_2d_info['sow_cost_1x']; sow_prof_2d_1x = day_2d_info['sow_pnl_1x']
            sow_cost_2d_2x = day_2d_info['sow_cost_2x']; sow_prof_2d_2x = day_2d_info['sow_pnl_2x']
        else:
            draws_2d = []
            wins_2d = 0; bets_2d_count = 0; planned_2d_count = 0; any_b_2d = False
            cost_2d_1x = 0; prof_2d_1x = 0
            cost_2d_alt = 0; prof_2d_alt = 0
            cost_2d_boost = 0; prof_2d_boost = 0
            cost_2d_2x = 0; prof_2d_2x = 0
            sow_cost_2d_1x = 0; sow_prof_2d_1x = 0
            sow_cost_2d_2x = 0; sow_prof_2d_2x = 0

        day_thai_name = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"][dt.weekday()]
        chrono_days.append({
            'date': d_str,
            'raw_date': f"{dt.day:02d}/{dt.month:02d}/{str(dt.year)[-2:]}",
            'day_name': f"วัน{day_thai_name}",
            'is_weekend': is_weekend,
            'is_live_today': is_live_today,
            'today_drawn_all': get_today_drawn_summary(lotteries, d_str) if is_live_today else [],
            'backup_2d_drawn': backup_2d_drawn,
            'use_b': use_b_3d,
            'any_b_2d': any_b_2d,
            'prev_lose_streak': prev_st_3d,
            'mult_3d_all': cur_m['all'],
            'mult_3d_alt': cur_m['alt'],
            'mult_3d_exp': cur_m['exp'],
            'mult_3d_sow': cur_m['sow'],
            'draws_count': drawn_3d_count,
            'planned_3d_count': len(day_draws_3d),
            'draws': day_draws_3d,
            'draws_2d': draws_2d,
            'wins_2d': wins_2d,
            'bets_2d_count': bets_2d_count,
            'planned_2d_count': planned_2d_count,
            # 2D Top 4 Hot Markets (mapped to _19d keys for seamless UI compatibility + boost mode)
            'bets_19d': cost_2d_1x,
            'profit_19d': prof_2d_1x,
            'bets_19d_alt': cost_2d_alt,
            'profit_19d_alt': prof_2d_alt,
            'bets_19d_boost': cost_2d_boost,
            'profit_19d_boost': prof_2d_boost,
            'bets_19d_2x': cost_2d_2x,
            'profit_19d_2x': prof_2d_2x,
            'bets_19d_exp': cost_2d_boost,
            'profit_19d_exp': prof_2d_boost,
            'sow_bets_19d': sow_cost_2d_1x,
            'sow_profit_19d': sow_prof_2d_1x,
            'sow_bets_19d_2x': sow_cost_2d_2x,
            'sow_profit_19d_2x': sow_prof_2d_2x,
            # 3D Cube Sniper
            'bets_3d': total_bets_3d,
            'payout_3d': total_payout_3d,
            'profit_3d': prof_3d_1x,
            'profit_3d_2x': prof_3d_2x,
            'profit_3d_alt': prof_3d_alt,
            'profit_3d_boost': prof_3d_alt,
            'profit_3d_exp': prof_3d_exp,
            'bets_3d_2x': total_bets_3d * cur_m['all'],
            'bets_3d_alt': total_bets_3d * cur_m['alt'],
            'bets_3d_boost': total_bets_3d * cur_m['alt'],
            'bets_3d_exp': total_bets_3d * cur_m['exp'],
            'sow_bets_3d': sow_bets_3d,
            'sow_profit_3d': prof_3d_sow_1x,
            'sow_profit_3d_2x': prof_3d_sow_2x,
            'sow_bets_3d_2x': sow_bets_3d * cur_m['sow'],
        })
        
        if drawn_3d_count > 0 and not is_live_today:
            cur_m['all'] = 2 if prof_3d_1x > 0 else 1
            cur_m['alt'] = (2 if cur_m['alt'] == 1 else 1) if prof_3d_1x > 0 else 1
            cur_m['exp'] = (cur_m['exp'] * 2) if prof_3d_1x > 0 else 1
            cur_m['sow'] = 2 if prof_3d_sow_1x > 0 else 1

    history_days = list(reversed(chrono_days))
    completed_days = [h for h in history_days if not h.get('is_live_today')]
    total_days = len(history_days)
    total_2d_days = len(valid_2d_dates)
    win_days_19d = sum(1 for h in completed_days if h['bets_2d_count'] > 0 and h['profit_19d_boost'] > 0)
    win_days_3d = sum(1 for h in completed_days if h['draws_count'] > 0 and h['profit_3d'] > 0)
    total_draws_2d = sum(h['bets_2d_count'] for h in completed_days)
    total_hits_2d = sum(h['wins_2d'] for h in completed_days)
    total_hits_3d = sum(sum(1 for d in h['draws'] if d['hit_3d']) for h in completed_days)
    
    stats_summary = {
        'total_days': total_days,
        'total_2d_days': total_2d_days,
        'win_days_19d': win_days_19d,
        'win_days_3d': win_days_3d,
        'total_draws_2d': total_draws_2d,
        'total_hits_2d': total_hits_2d,
        'total_hits_3d': total_hits_3d,
        'thai_today': today_str,
        'thai_now': get_thai_now().strftime('%d/%m/%Y %H:%M:%S น.')
    }
    
    return history_days, stats_summary

def build_picks_payload(target_d=None):
    picks_3d, picks_2d_top4, picks_2d_backup, is_weekend, use_formula_b, prev_streak, today_drawn, date_str = calculate_picks(target_d)
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    day_thai_name = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"][dt.weekday()]
    return {
        'picks': picks_3d,
        'picks_2d_top4': picks_2d_top4,
        'picks_2d_backup': picks_2d_backup,
        'is_weekend': is_weekend,
        'use_formula_b': use_formula_b,
        'prev_lose_streak': prev_streak,
        'today_drawn': today_drawn,
        'date': date_str,
        'raw_date': f"{dt.day:02d}/{dt.month:02d}/{str(dt.year)[-2:]}",
        'day_name': f"วัน{day_thai_name}",
        'thai_now': get_thai_now().strftime('%d/%m/%Y %H:%M:%S น.')
    }

@app.route('/api/picks')
def api_picks():
    target_d = request.args.get('date')
    return jsonify(build_picks_payload(target_d))

@app.route('/api/history')
def api_history():
    history_days, stats_summary = generate_history_data()
    return jsonify({
        'history': history_days,
        'stats': stats_summary
    })

@app.route('/api/sync', methods=['POST'])
def api_sync():
    logs = sync_yahoo_finance()
    picks_payload = build_picks_payload()
    history_days, stats_summary = generate_history_data()
    return jsonify({
        'status': 'success', 
        'logs': logs, 
        'timestamp': get_thai_now().strftime('%Y-%m-%d %H:%M:%S'),
        'picks_payload': picks_payload,
        'history_payload': {
            'history': history_days,
            'stats': stats_summary
        }
    })

@app.route('/')
def index():
    local_ip = get_local_ip()
    return render_template_string(HTML_TEMPLATE, local_ip=local_ip)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <meta name="theme-color" content="#0B0F19">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <title>Simons Quant Sniper App</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    fontFamily: { sans: ['Prompt', 'sans-serif'] },
                    colors: {
                        brand: { 500: '#10B981', 600: '#059669', 700: '#047857' },
                        darkBg: '#0B0F19',
                        darkCard: '#151D30',
                        darkBorder: '#23304E'
                    }
                }
            }
        }
    </script>
    <style>
        body { font-family: 'Prompt', sans-serif; background-color: #0B0F19; color: #F3F4F6; }
        .glass { background: rgba(21, 29, 48, 0.9); backdrop-filter: blur(14px); border: 1px solid rgba(35, 48, 78, 0.7); }
        .active-tab-nav { color: #10B981 !important; }
        .active-tab-nav i { transform: scale(1.15); }
        * { -webkit-tap-highlight-color: transparent; }
    </style>
</head>
<body class="pb-28 select-none antialiased min-h-screen">

    <!-- Top App Header -->
    <header class="sticky top-0 z-40 glass px-4 py-3 flex items-center justify-between border-b border-darkBorder shadow-lg">
        <div class="flex items-center space-x-2.5">
            <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-500 to-teal-400 flex items-center justify-center shadow-emerald-500/30 shadow-lg">
                <i class="fa-solid fa-crosshairs text-slate-900 text-lg font-black"></i>
            </div>
            <div>
                <h1 class="font-extrabold text-base tracking-wide bg-gradient-to-r from-emerald-400 to-teal-200 bg-clip-text text-transparent">Simons Quant Pro</h1>
                <p class="text-[10px] text-emerald-400 font-medium flex items-center gap-1">
                    <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                    <span id="headerSub">2D Top 4 Hot (+สูตร B) & 3D Sniper</span>
                </p>
            </div>
        </div>
        <button onclick="triggerSync()" id="syncBtn" class="px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold flex items-center gap-1.5 active:scale-95 transition hover:bg-emerald-500/20">
            <i class="fa-solid fa-arrows-rotate text-xs" id="syncIcon"></i>
            <span>ซิงค์ผลสด</span>
        </button>
    </header>

    <!-- Toast Notification -->
    <div id="toast" class="fixed top-16 left-4 right-4 z-50 transform -translate-y-24 opacity-0 transition-all duration-300 pointer-events-none">
        <div class="glass p-3 rounded-2xl border border-emerald-500/50 shadow-2xl flex items-center gap-3 bg-darkCard/95">
            <div class="w-8 h-8 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center">
                <i class="fa-solid fa-check text-lg"></i>
            </div>
            <div class="text-xs">
                <p class="font-bold text-white" id="toastTitle">คัดลอกสำเร็จ</p>
                <p class="text-gray-400" id="toastMsg">คัดลอกชุดตัวเลขเรียบร้อยแล้ว</p>
            </div>
        </div>
    </div>

    <!-- MAIN CONTAINER -->
    <main class="p-4 max-w-lg mx-auto">

        <!-- ============================================================= -->
        <!-- TAB 1: 🎯 วันนี้แทงอะไร (TODAY'S PICKS) -->
        <!-- ============================================================= -->
        <section id="tabPicks" class="space-y-4">
            <div class="flex items-center justify-between">
                <div>
                    <h2 class="text-lg font-black text-white flex items-center gap-2">
                        <i class="fa-solid fa-crosshairs text-emerald-400"></i> วันนี้แทงอะไร
                    </h2>
                    <p class="text-xs text-gray-400" id="picksDateHeader">งวดประจำวัน (อัปเดตอัตโนมัติ)</p>
                </div>
                <span id="marketBadge" class="px-2.5 py-1 text-[11px] font-semibold rounded-full bg-slate-800 border border-slate-700 text-emerald-400">
                    ตลาดหุ้นหลัก
                </span>
            </div>

            <!-- Live Today Drawn Markets Banner -->
            <div id="todayDrawnBanner" class="glass rounded-2xl p-3 border border-teal-500/40 bg-slate-900/80 space-y-1.5 hidden">
                <div class="flex items-center justify-between text-[11px]">
                    <span class="font-extrabold text-teal-300 flex items-center gap-1.5">
                        <span class="w-2 h-2 rounded-full bg-teal-400 animate-ping"></span>
                        <span id="todayDrawnTitle">ผลหวยที่ออกแล้ววันนี้</span>
                    </span>
                    <span class="text-[10px] text-gray-400" id="thaiClockText">เวลาไทย: -</span>
                </div>
                <div id="todayDrawnList" class="flex flex-wrap gap-1.5 pt-0.5"></div>
            </div>

            <div id="picksLoading" class="py-16 text-center text-gray-400 space-y-2">
                <i class="fa-solid fa-circle-notch fa-spin text-3xl text-emerald-400"></i>
                <p class="text-xs font-medium">กำลังคำนวณสูตร 2D คัด 4 ตลาดฮอต & 3D Cube Sniper...</p>
            </div>

            <!-- 1. 🔥 2D TOP 4 HOT MARKETS SECTION -->
            <div id="picks2dSection" class="space-y-3 hidden">
                <div class="glass rounded-2xl p-3.5 border border-emerald-500/40 bg-gradient-to-r from-emerald-500/15 to-slate-900 space-y-2">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <span class="px-2 py-0.5 rounded-lg bg-emerald-500/30 text-emerald-200 font-extrabold text-xs border border-emerald-400/40">🔥 สูตรเลข 2 ตัว (จ่าย 92)</span>
                            <span class="text-xs text-white font-bold">คัดมาแทงแค่ 4 ตลาด/วัน</span>
                        </div>
                        <span class="text-[10px] font-bold text-amber-300 bg-amber-500/15 px-2 py-0.5 rounded border border-amber-500/30">แม่น 48.7% | ROI +34.1%</span>
                    </div>
                    <p class="text-[11px] text-gray-300 leading-relaxed" id="picks2dSummaryText">
                        ใช้ทุนน้อย ~180–193฿/วัน (สลับสูตร B แก้ทางวันที่ 3 อัตโนมัติ) กำไร 4 เดือน +4,001฿ ถึง +4,940฿
                    </p>
                </div>

                <div id="picks2dContainer" class="space-y-3"></div>

                <!-- Toggle Backup 4 Markets -->
                <div class="pt-1">
                    <button onclick="toggleBackup2d()" id="btnToggleBackup2d" class="w-full py-2 px-3 rounded-xl bg-slate-900/80 border border-slate-700 text-gray-400 text-xs font-semibold flex items-center justify-center gap-2 hover:text-white transition">
                        <i class="fa-solid fa-chevron-down" id="iconBackup2d"></i>
                        <span id="btnToggleBackup2dText">ดูอีก 4 ตลาดสำรอง (กรณีต้องการแทงครบ 8 ตลาด)</span>
                    </button>
                    <div id="picks2dBackupContainer" class="space-y-3 mt-3 hidden"></div>
                </div>
            </div>

            <!-- 2. 🎯 3D CUBE SNIPER SECTION -->
            <div id="picks3dSection" class="space-y-3 pt-2 hidden">
                <div id="regimeBanner" class="glass rounded-2xl p-3 border border-orange-500/40 bg-gradient-to-r from-orange-500/10 to-slate-900"></div>
                <div id="picksContainer" class="space-y-3"></div>
            </div>
        </section>


        <!-- ============================================================= -->
        <!-- TAB 2: ✅ ตรวจผลรางวัล ถูก/ผิด (RESULTS VERIFICATION & PNL) -->
        <!-- ============================================================= -->
        <section id="tabResults" class="space-y-4 hidden">
            <div class="flex items-center justify-between">
                <div>
                    <h2 class="text-lg font-black text-white flex items-center gap-2">
                        <i class="fa-solid fa-square-check text-teal-400"></i> ตรวจผล ถูก / ผิด & กำไรทุกวัน
                    </h2>
                    <p class="text-xs text-gray-400" id="resSubHeader">แยกวันจันทร์–ศุกร์ (หวยหุ้น) และ เสาร์–อาทิตย์ (หวยวันหยุด)</p>
                </div>
                <span class="px-2.5 py-1 text-[11px] font-bold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30" id="resTotalDays">
                    - วัน
                </span>
            </div>

            <!-- Day-Group Switcher: แยกวัน จันทร์-ศุกร์ vs เสาร์-อาทิตย์ ออกจากกัน 100% -->
            <div class="glass p-2 rounded-2xl border border-teal-500/40 bg-slate-900/90 grid grid-cols-2 gap-2 shadow-lg">
                <button onclick="setDayGroup('wd')" id="btnDayWd" class="py-2.5 px-2 rounded-xl text-xs font-extrabold border transition flex items-center justify-center gap-1.5 bg-emerald-500/25 text-emerald-300 border-emerald-400/50 shadow">
                    💼 จันทร์ – ศุกร์ (หวยหุ้น)
                </button>
                <button onclick="setDayGroup('we')" id="btnDayWe" class="py-2.5 px-2 rounded-xl text-xs font-bold border transition flex items-center justify-center gap-1.5 bg-slate-900/60 text-gray-400 border-slate-700">
                    🌴 เสาร์ – อาทิตย์ (วันหยุด)
                </button>
            </div>

            <!-- Staking & Play Mode Selector -->
            <div class="glass p-3 rounded-2xl border border-darkBorder bg-darkCard/90 space-y-2">
                <div class="flex justify-between items-center text-xs">
                    <span class="font-bold text-gray-300 flex items-center gap-1.5">
                        <i class="fa-solid fa-bolt text-amber-400"></i> โหมดเดินเงิน:
                    </span>
                    <span class="text-[10px] text-amber-300 font-bold" id="playModeDesc">สลับ 1x↔2x + อัด 2x สูตร B วันที่ 3 🚀 (+4,940฿)</span>
                </div>
                <div class="grid grid-cols-2 gap-1.5">
                    <button onclick="setPlayMode('boost_b')" id="pm_boost_b" class="py-1.5 px-2 rounded-xl text-[11px] font-bold border transition bg-emerald-500/20 text-emerald-300 border-emerald-500/40">
                        อัด 2x สูตร B + สลับ 1x↔2x 🚀
                    </button>
                    <button onclick="setPlayMode('all_alt')" id="pm_all_alt" class="py-1.5 px-2 rounded-xl text-[11px] font-bold border transition bg-slate-900/60 text-gray-400 border-slate-700">
                        ถูกสลับฟันปลา 1x ↔ 2x 🔄
                    </button>
                    <button onclick="setPlayMode('all_1x')" id="pm_all_1x" class="py-1.5 px-2 rounded-xl text-[11px] font-bold border transition bg-slate-900/60 text-gray-400 border-slate-700">
                        แทงคงที่ 1x ตลอด 🛡️
                    </button>
                    <button onclick="setPlayMode('all_2x')" id="pm_all_2x" class="py-1.5 px-2 rounded-xl text-[11px] font-bold border transition bg-slate-900/60 text-gray-400 border-slate-700">
                        ถูกแช่ 2x ยาว 🔥
                    </button>
                    <button onclick="setPlayMode('sow_1x')" id="pm_sow_1x" class="py-1.5 px-2 rounded-xl text-[11px] font-bold border transition bg-slate-900/60 text-gray-400 border-slate-700">
                        ถูกปุ๊บหยุดปั๊บ (1x)
                    </button>
                    <button onclick="setPlayMode('sow_2x')" id="pm_sow_2x" class="py-1.5 px-2 rounded-xl text-[11px] font-bold border transition bg-slate-900/60 text-gray-400 border-slate-700">
                        ถูกหยุด + อัด 2x 🚀
                    </button>
                </div>
            </div>

            <!-- Quick Summary Card -->
            <div class="glass rounded-2xl p-4 border border-emerald-500/30 bg-gradient-to-br from-darkCard to-slate-900 shadow-xl space-y-3">
                <div class="flex justify-between items-center border-b border-darkBorder/60 pb-2.5">
                    <span class="text-xs font-bold text-gray-300 flex items-center gap-1.5" id="summaryCardTitle">
                        <i class="fa-solid fa-fire text-amber-400"></i> ผลตอบแทนสะสม (วันจันทร์ – ศุกร์)
                    </span>
                    <span class="text-[11px] font-bold text-emerald-400" id="cardRoiText">ความแม่น 2D: 146/300 ไม้ (48.7%)</span>
                </div>
                <div class="grid grid-cols-2 gap-2.5 text-center" id="summaryGrid2Cols">
                    <div class="p-2.5 rounded-xl bg-slate-900/60 border border-emerald-500/30" id="summaryBox2d">
                        <p class="text-[10px] text-gray-400">🔥 2 ตัว (คัด 4 ตลาด/วัน)</p>
                        <p class="text-base font-extrabold text-emerald-400 mt-0.5" id="cardProfit19d">+0 ฿</p>
                    </div>
                    <div class="p-2.5 rounded-xl bg-slate-900/60 border border-orange-500/30" id="summaryBox3d">
                        <p class="text-[10px] text-gray-400" id="labelProfit3d">🎯 3 ตัวบน (สูตร A + สลับ B วันที่ 3)</p>
                        <p class="text-base font-extrabold text-orange-400 mt-0.5" id="cardProfit3d">+0 ฿</p>
                    </div>
                </div>
                <div class="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex justify-between items-center mt-2">
                    <span class="text-xs text-emerald-400 font-medium" id="labelTotalProfitAll">กำไรสุทธิรวมตามสูตรที่เลือก (จ–ศ)</span>
                    <span class="text-lg font-black text-emerald-400" id="cardTotalProfitAll">+0 ฿</span>
                </div>
            </div>
            
            <!-- Model Selection Filter Control Bar (shown on Mon-Fri) -->
            <div id="modelFilterBox" class="glass p-3.5 rounded-2xl border border-darkBorder bg-darkCard/80 space-y-2">
                <div class="flex justify-between items-center text-xs">
                    <span class="font-extrabold text-gray-200 flex items-center gap-1.5">
                        <i class="fa-solid fa-sliders text-teal-400"></i> เลือกแสดงผลสูตร (กดเปิด/ปิดแยกดูได้):
                    </span>
                    <span class="text-[10px] text-emerald-400 font-bold" id="filterStatusText">รวมทั้ง 2 สูตรหลัก</span>
                </div>
                <div class="grid grid-cols-2 gap-2">
                    <button onclick="toggleModelFilter('19d')" id="btnFilter19d" class="py-2 px-2 rounded-xl text-xs font-bold border transition flex items-center justify-center gap-1.5 bg-emerald-500/20 text-emerald-300 border-emerald-500/40 active:scale-95">
                        <i class="fa-solid fa-square-check" id="iconFilter19d"></i> 🔥 2 ตัว (คัด 4 ตลาด)
                    </button>
                    <button onclick="toggleModelFilter('3d')" id="btnFilter3d" class="py-2 px-2 rounded-xl text-xs font-bold border transition flex items-center justify-center gap-1.5 bg-orange-500/20 text-orange-300 border-orange-500/40 active:scale-95">
                        <i class="fa-solid fa-square-check" id="iconFilter3d"></i> 🎯 3 ตัว (สูตร A+B)
                    </button>
                </div>
            </div>

            <!-- Cumulative Profit Chart -->
            <div class="glass rounded-2xl p-4 border border-darkBorder shadow-xl bg-darkCard/50">
                <div class="flex justify-between items-center mb-2">
                    <span class="text-xs font-bold text-gray-300" id="chartTitleText"><i class="fa-solid fa-chart-area text-blue-400"></i> กราฟกำไรสะสมรายวัน (จันทร์ – ศุกร์)</span>
                </div>
                <div class="relative h-48 w-full">
                    <canvas id="profitChart"></canvas>
                </div>
            </div>

            <div id="historyLoading" class="py-16 text-center text-gray-400 space-y-2">
                <i class="fa-solid fa-circle-notch fa-spin text-3xl text-teal-400"></i>
                <p class="text-xs font-medium">กำลังโหลดประวัติผลกำไรขาดทุนครบทุกวัน...</p>
            </div>

            <div id="historyContainer" class="space-y-3.5 hidden"></div>
        </section>


        <!-- ============================================================= -->
        <!-- TAB 3: 📊 สถิติ & พอร์ตภาพรวม (STATS & INSIGHTS) -->
        <!-- ============================================================= -->
        <section id="tabStats" class="space-y-4 hidden">
            <div>
                <h2 class="text-lg font-black text-white flex items-center gap-2">
                    <i class="fa-solid fa-chart-pie text-emerald-400"></i> สถิติ & ประสิทธิภาพพอร์ต (แยก จ-ศ / ส-อา)
                </h2>
                <p class="text-xs text-gray-400">สรุปสถิติแยกวันจันทร์–ศุกร์ (หวยหุ้น) และ วันเสาร์–อาทิตย์ (หวยวันหยุด)</p>
            </div>

            <div class="glass rounded-2xl p-4 border border-emerald-500/30 space-y-3">
                <h3 class="text-xs font-bold text-emerald-300 flex items-center gap-1.5">
                    <i class="fa-solid fa-fire"></i> 💼 วันจันทร์ – ศุกร์: สูตร 2 ตัว (คัด 4 ตลาดฮอต/วัน + สลับสูตร B วันที่ 3)
                </h3>
                <div class="space-y-2 text-xs">
                    <div class="flex justify-between py-1 border-b border-darkBorder/40">
                        <span class="text-gray-400">ความแม่นยำรายไม้ (75 วันทำการ)</span>
                        <span class="font-bold text-emerald-300">ถูก 146 / 300 ไม้ (48.7%)</span>
                    </div>
                    <div class="flex justify-between py-1 border-b border-darkBorder/40">
                        <span class="text-gray-400">จำนวนวันบวก / วันติดลบ</span>
                        <span class="font-bold text-white">บวก 52 วัน (69.3%) / ลบ 23 วัน</span>
                    </div>
                    <div class="flex justify-between py-1 border-b border-darkBorder/40">
                        <span class="text-gray-400">1. โหมดคงที่ 1x (ทุน ~138฿/วัน)</span>
                        <span class="font-bold text-emerald-400">+3,091 ฿ (ROI +29.9%, MaxDD -179฿)</span>
                    </div>
                    <div class="flex justify-between py-1 border-b border-darkBorder/40">
                        <span class="text-gray-400">2. โหมดสลับ 1x↔2x (ทุน ~182฿/วัน)</span>
                        <span class="font-bold text-emerald-400">+4,001 ฿ (ROI +29.3%, MaxDD -301฿)</span>
                    </div>
                    <div class="flex justify-between pt-1 font-bold text-sm">
                        <span class="text-amber-300">3. โหมดอัด 2x สูตร B วันที่ 3 (ทุน ~193฿/วัน)</span>
                        <span class="text-amber-300">+4,940 ฿ (ROI +34.1%) 🏆</span>
                    </div>
                </div>
            </div>

            <div class="glass rounded-2xl p-4 border border-darkBorder space-y-3">
                <h3 class="text-xs font-bold text-teal-300 flex items-center gap-1.5">
                    <i class="fa-solid fa-briefcase"></i> สรุปแยกพอร์ต จันทร์–ศุกร์ vs เสาร์–อาทิตย์ (ตามโหมดที่เลือก)
                </h3>
                <div class="space-y-2 text-xs">
                    <div class="flex justify-between py-1 border-b border-darkBorder/40">
                        <span class="text-gray-400">💼 วันจันทร์ – ศุกร์ (หวยหุ้น)</span>
                        <span class="font-bold text-white" id="statWdWinLoss">-</span>
                    </div>
                    <div class="flex justify-between py-1 border-b border-darkBorder/40">
                        <span class="text-gray-400">กำไรสุทธิ จันทร์ – ศุกร์</span>
                        <span class="font-bold text-emerald-400" id="statWdProfit">-</span>
                    </div>
                    <div class="flex justify-between py-1 border-b border-darkBorder/40">
                        <span class="text-gray-400">🌴 วันเสาร์ – อาทิตย์ (หวยวันหยุด 3D)</span>
                        <span class="font-bold text-white" id="statWeWinLoss">-</span>
                    </div>
                    <div class="flex justify-between pt-1 font-bold text-sm">
                        <span class="text-gray-300">กำไรสุทธิ เสาร์ – อาทิตย์</span>
                        <span class="text-emerald-400" id="statWeProfit">-</span>
                    </div>
                </div>
            </div>
        </section>

    </main>

    <!-- Bottom Navigation Bar (Fixed for Mobile) -->
    <nav class="fixed bottom-0 left-0 right-0 z-50 glass border-t border-darkBorder py-2 px-6 flex justify-around items-center max-w-lg mx-auto shadow-2xl bg-darkCard/95">
        <button onclick="switchTab('picks')" id="navPicks" class="flex flex-col items-center gap-1 text-xs font-semibold text-gray-400 active-tab-nav transition">
            <i class="fa-solid fa-crosshairs text-lg"></i>
            <span>แทงวันนี้</span>
        </button>
        <button onclick="switchTab('results')" id="navResults" class="flex flex-col items-center gap-1 text-xs font-semibold text-gray-400 transition">
            <i class="fa-solid fa-square-check text-lg"></i>
            <span>ตรวจผล / กำไร</span>
        </button>
        <button onclick="switchTab('stats')" id="navStats" class="flex flex-col items-center gap-1 text-xs font-semibold text-gray-400 transition">
            <i class="fa-solid fa-chart-pie text-lg"></i>
            <span>สถิติรวม</span>
        </button>
    </nav>

    <script>
        let currentTab = 'picks';
        let historyData = null;
        let profitChartInstance = null;
        let selectedModels = { '19d': true, '3d': true };
        let playMode = 'boost_b'; // 'boost_b', 'all_alt', 'all_1x', 'all_2x', 'sow_1x', 'sow_2x'
        let dayGroup = 'wd'; // 'wd' = จันทร์-ศุกร์ (หวยหุ้น), 'we' = เสาร์-อาทิตย์ (หวยวันหยุด)
        let showBackup2d = false;

        function switchTab(tab) {
            currentTab = tab;
            
            document.getElementById('tabPicks').classList.add('hidden');
            document.getElementById('tabResults').classList.add('hidden');
            document.getElementById('tabStats').classList.add('hidden');
            
            document.getElementById('navPicks').classList.remove('active-tab-nav');
            document.getElementById('navResults').classList.remove('active-tab-nav');
            document.getElementById('navStats').classList.remove('active-tab-nav');
            
            if (tab === 'picks') {
                document.getElementById('tabPicks').classList.remove('hidden');
                document.getElementById('navPicks').classList.add('active-tab-nav');
            } else if (tab === 'results') {
                document.getElementById('tabResults').classList.remove('hidden');
                document.getElementById('navResults').classList.add('active-tab-nav');
                if (!historyData) loadHistory();
                else renderFilteredHistory();
            } else if (tab === 'stats') {
                document.getElementById('tabStats').classList.remove('hidden');
                document.getElementById('navStats').classList.add('active-tab-nav');
                if (!historyData) loadHistory();
                else renderFilteredHistory();
            }
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        function setDayGroup(group) {
            dayGroup = group;
            const btnWd = document.getElementById('btnDayWd');
            const btnWe = document.getElementById('btnDayWe');
            const modelBox = document.getElementById('modelFilterBox');
            const box2d = document.getElementById('summaryBox2d');
            const grid2Cols = document.getElementById('summaryGrid2Cols');

            if (group === 'wd') {
                btnWd.className = 'py-2.5 px-2 rounded-xl text-xs font-extrabold border transition flex items-center justify-center gap-1.5 bg-emerald-500/25 text-emerald-300 border-emerald-400/50 shadow';
                btnWe.className = 'py-2.5 px-2 rounded-xl text-xs font-bold border transition flex items-center justify-center gap-1.5 bg-slate-900/60 text-gray-400 border-slate-700';
                modelBox.classList.remove('hidden');
                box2d.classList.remove('hidden');
                grid2Cols.className = 'grid grid-cols-2 gap-2.5 text-center';
                document.getElementById('summaryCardTitle').innerHTML = '<i class="fa-solid fa-fire text-amber-400"></i> ผลตอบแทนสะสม (วันจันทร์ – ศุกร์: หวยหุ้น)';
                document.getElementById('labelProfit3d').innerText = '🎯 3 ตัวบน (สูตร A + สลับ B วันที่ 3)';
                document.getElementById('labelTotalProfitAll').innerText = 'กำไรสุทธิรวมตามสูตรที่เลือก (จันทร์ – ศุกร์)';
                document.getElementById('chartTitleText').innerHTML = '<i class="fa-solid fa-chart-area text-blue-400"></i> กราฟกำไรสะสมรายวัน (วันจันทร์ – ศุกร์)';
            } else {
                btnWe.className = 'py-2.5 px-2 rounded-xl text-xs font-extrabold border transition flex items-center justify-center gap-1.5 bg-amber-500/25 text-amber-300 border-amber-400/50 shadow';
                btnWd.className = 'py-2.5 px-2 rounded-xl text-xs font-bold border transition flex items-center justify-center gap-1.5 bg-slate-900/60 text-gray-400 border-slate-700';
                modelBox.classList.add('hidden');
                box2d.classList.add('hidden');
                grid2Cols.className = 'grid grid-cols-1 gap-2.5 text-center';
                document.getElementById('summaryCardTitle').innerHTML = '<i class="fa-solid fa-umbrella-beach text-amber-400"></i> ผลตอบแทนสะสม (วันเสาร์ – อาทิตย์: หวยวันหยุด)';
                document.getElementById('labelProfit3d').innerText = '🎯 3 ตัวบน หวยวันหยุด (ฮานอยพิเศษ/ปกติ/VIP & ลาว Super)';
                document.getElementById('labelTotalProfitAll').innerText = 'กำไรสุทธิรวม (วันเสาร์ – อาทิตย์)';
                document.getElementById('chartTitleText').innerHTML = '<i class="fa-solid fa-chart-area text-amber-400"></i> กราฟกำไรสะสมรายวัน (วันเสาร์ – อาทิตย์)';
            }
            if (historyData) renderFilteredHistory();
        }

        function toggleBackup2d() {
            showBackup2d = !showBackup2d;
            const c = document.getElementById('picks2dBackupContainer');
            const ic = document.getElementById('iconBackup2d');
            if (showBackup2d) {
                c.classList.remove('hidden');
                ic.className = 'fa-solid fa-chevron-up';
            } else {
                c.classList.add('hidden');
                ic.className = 'fa-solid fa-chevron-down';
            }
        }

        function setPlayMode(mode) {
            playMode = mode;
            const modes = ['boost_b', 'all_alt', 'all_1x', 'all_2x', 'sow_1x', 'sow_2x'];
            const descMap = {
                'boost_b': 'สลับ 1x↔2x + อัด 2x สูตร B วันที่ 3 🚀 (+4,940฿ / ROI +34.1%)',
                'all_alt': 'ถูกสลับฟันปลา 1x ↔ 2x 🔄 (+4,001฿ / ROI +29.3%)',
                'all_1x': 'แทงคงที่ 1x ตลอด 🛡️ (+3,091฿ / ROI +29.9%)',
                'all_2x': 'ถูกแช่ 2x ยาวจนผิด 🔥',
                'sow_1x': 'ถูกปุ๊บหยุดปั๊บรายวัน (1x)',
                'sow_2x': 'ถูกปุ๊บหยุดปั๊บ + อัด 2x 🚀'
            };
            document.getElementById('playModeDesc').innerText = descMap[mode] || '';
            modes.forEach(m => {
                const btn = document.getElementById('pm_' + m);
                if (!btn) return;
                if (m === mode) {
                    btn.className = 'py-1.5 px-2 rounded-xl text-[11px] font-bold border transition bg-emerald-500/20 text-emerald-300 border-emerald-500/40';
                } else {
                    btn.className = 'py-1.5 px-2 rounded-xl text-[11px] font-bold border transition bg-slate-900/60 text-gray-400 border-slate-700';
                }
            });
            if (historyData) renderFilteredHistory();
        }

        function getDayModelProfit(h, modelKey) {
            if (modelKey === '3d') {
                if (playMode === 'all_1x') return h.profit_3d;
                if (playMode === 'all_2x') return h.profit_3d_2x;
                if (playMode === 'all_alt') return h.profit_3d_alt;
                if (playMode === 'boost_b') return h.profit_3d_boost;
                if (playMode === 'sow_1x') return h.sow_profit_3d;
                if (playMode === 'sow_2x') return h.sow_profit_3d_2x;
            } else if (modelKey === '19d') {
                if (playMode === 'all_1x') return h.profit_19d;
                if (playMode === 'all_2x') return h.profit_19d_2x;
                if (playMode === 'all_alt') return h.profit_19d_alt;
                if (playMode === 'boost_b') return h.profit_19d_boost;
                if (playMode === 'sow_1x') return h.sow_profit_19d;
                if (playMode === 'sow_2x') return h.sow_profit_19d_2x;
            }
            return 0;
        }

        function getDayModelBets(h, modelKey) {
            if (modelKey === '3d') {
                if (playMode === 'all_1x') return h.bets_3d;
                if (playMode === 'all_2x') return h.bets_3d_2x;
                if (playMode === 'all_alt') return h.bets_3d_alt;
                if (playMode === 'boost_b') return h.bets_3d_boost;
                if (playMode === 'sow_1x') return h.sow_bets_3d;
                if (playMode === 'sow_2x') return h.sow_bets_3d_2x;
            } else if (modelKey === '19d') {
                if (playMode === 'all_1x') return h.bets_19d;
                if (playMode === 'all_2x') return h.bets_19d_2x;
                if (playMode === 'all_alt') return h.bets_19d_alt;
                if (playMode === 'boost_b') return h.bets_19d_boost;
                if (playMode === 'sow_1x') return h.sow_bets_19d;
                if (playMode === 'sow_2x') return h.sow_bets_19d_2x;
            }
            return 0;
        }

        function build2dCardHtml(it, isBackup) {
            const targetBadge = it.target === 'TOP2'
                ? `<span class="px-2 py-0.5 rounded-lg bg-amber-500/20 text-amber-300 font-extrabold text-xs border border-amber-500/40">🔼 แทง 2 ตัวบน</span>`
                : `<span class="px-2 py-0.5 rounded-lg bg-cyan-500/20 text-cyan-300 font-extrabold text-xs border border-cyan-500/40">🔽 แทง 2 ตัวล่าง</span>`;

            const formulaBadge = it.use_formula_b
                ? `<span class="px-2 py-0.5 rounded-lg bg-purple-500/30 text-purple-200 font-extrabold text-[11px] border border-purple-400/50">🔄 ${it.formula_label}</span>`
                : `<span class="px-2 py-0.5 rounded-lg bg-emerald-500/20 text-emerald-300 font-bold text-[11px] border border-emerald-500/40">${it.formula_label}</span>`;

            let statusRight = '';
            if (it.actual_top3) {
                const hitCls = it.hit ? 'bg-emerald-500/25 text-emerald-300 border-emerald-500/50' : 'bg-rose-500/25 text-rose-300 border-rose-500/50';
                const hitIcon = it.hit ? '✅ เข้า!' : '❌ หลุด';
                statusRight = `<span class="text-[11px] font-extrabold ${hitCls} border px-2.5 py-0.5 rounded-full">${hitIcon} บน:${it.actual_top3} | ล่าง:${it.actual_bot2}</span>`;
            } else {
                statusRight = `<span class="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded-full">⏳ รอผล ${it.draw_time} (ฮอต ${it.score})</span>`;
            }

            let numbersDetailHtml = '';
            if (it.root_digits && it.root_digits.length > 0) {
                const pills = it.root_digits.map(d => `<span class="px-2.5 py-0.5 rounded-lg bg-emerald-500/25 text-emerald-200 font-extrabold text-sm border border-emerald-400/40">${d}</span>`).join(' ');
                numbersDetailHtml = `
                    <div class="flex items-center justify-between bg-slate-950/60 p-2 rounded-lg border border-darkBorder/60 text-xs">
                        <span class="text-gray-300 font-medium">${it.method_short} (${it.target_thai}):</span>
                        <div class="flex items-center gap-1.5"><span class="text-gray-400 text-[11px]">เลขเด่น:</span> ${pills}</div>
                    </div>
                `;
            } else {
                const tPills = (it.tens || []).map(d => `<span class="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold text-xs border border-emerald-500/30">${d}</span>`).join(' ');
                const uPills = (it.units || []).map(d => `<span class="px-1.5 py-0.5 rounded bg-teal-500/20 text-teal-300 font-bold text-xs border border-teal-500/30">${d}</span>`).join(' ');
                numbersDetailHtml = `
                    <div class="text-[11px] text-gray-300 space-y-1 bg-slate-950/60 p-2 rounded-lg border border-darkBorder/60">
                        <div class="flex items-center gap-1.5 flex-wrap"><span class="text-gray-400 w-14">หลักสิบ:</span> ${tPills}</div>
                        <div class="flex items-center gap-1.5 flex-wrap"><span class="text-gray-400 w-14">หลักหน่วย:</span> ${uPills}</div>
                    </div>
                `;
            }

            const rankBadge = isBackup
                ? `<span class="px-2 py-0.5 rounded bg-slate-800 text-gray-400 text-[10px] font-bold border border-slate-700">สำรอง #${it.rank}</span>`
                : `<span class="px-2 py-0.5 rounded bg-emerald-500 text-slate-950 text-[11px] font-black">🎯 คัดตัวจริง #${it.rank}</span>`;

            return `
                <div class="glass rounded-2xl p-3.5 border ${it.use_formula_b ? 'border-purple-500/50' : (isBackup ? 'border-slate-700/70 opacity-85' : 'border-emerald-500/40')} space-y-2.5 shadow-lg">
                    <div class="flex items-center justify-between border-b border-darkBorder/50 pb-2">
                        <div class="space-y-0.5">
                            <div class="flex items-center gap-2">
                                ${rankBadge}
                                <h3 class="font-extrabold text-sm text-white">${it.name}</h3>
                            </div>
                            <p class="text-[11px] text-gray-400">ปิดรับ: <span class="text-emerald-400 font-semibold">${it.draw_time}</span></p>
                        </div>
                        ${statusRight}
                    </div>

                    <div class="flex items-center justify-between flex-wrap gap-1.5">
                        ${targetBadge}
                        ${formulaBadge}
                    </div>

                    <div class="grid grid-cols-3 gap-1.5 text-center text-[10px] bg-slate-900/80 p-1.5 rounded-xl border border-darkBorder/50">
                        <div class="p-1 rounded bg-slate-950/60">
                            <p class="text-gray-400">คงที่ 1x</p>
                            <p class="font-bold text-white">1x (${it.cost_1x}฿)</p>
                        </div>
                        <div class="p-1 rounded bg-slate-950/60 border border-emerald-500/20">
                            <p class="text-gray-400">สลับ 1x↔2x</p>
                            <p class="font-bold text-emerald-300">${it.m_alt}x (${it.cost_alt}฿)</p>
                        </div>
                        <div class="p-1 rounded bg-slate-950/60 border border-amber-500/30">
                            <p class="text-gray-400">อัดสูตร B 2x</p>
                            <p class="font-extrabold text-amber-300">${it.m_boost}x (${it.cost_boost}฿)</p>
                        </div>
                    </div>

                    ${numbersDetailHtml}

                    <div class="grid grid-cols-2 gap-2 pt-0.5">
                        <button onclick="copyRaw('${it.nums_comma}', '${it.target_thai} (${it.nums_count} ตัว) คั่นจุลภาค', '${it.name}')" class="py-2 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 text-xs font-bold flex items-center justify-center gap-1.5 active:scale-95 transition">
                            <i class="fa-regular fa-copy"></i> คัดลอก ${it.target_thai} (${it.nums_count})
                        </button>
                        <button onclick="copyRaw('${it.nums_space}', '${it.target_thai} (${it.nums_count} ตัว) เว้นวรรค', '${it.name}')" class="py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-600 text-gray-300 text-xs font-semibold flex items-center justify-center gap-1.5 active:scale-95 transition">
                            <i class="fa-solid fa-font"></i> คัดลอก (เว้นวรรค)
                        </button>
                    </div>
                </div>
            `;
        }

        function renderPicksData(data) {
            document.getElementById('picksDateHeader').innerText = `งวด${data.day_name || ''}ที่ ${data.raw_date || data.date} (${data.date})`;
            document.getElementById('marketBadge').innerText = data.is_weekend ? '🌴 หวยวันหยุด (ส-อา)' : '💼 ตลาดหุ้นหลัก (จ-ศ)';

            // Render Live Today Drawn Banner
            const drawnBanner = document.getElementById('todayDrawnBanner');
            const drawnList = document.getElementById('todayDrawnList');
            const clockText = document.getElementById('thaiClockText');
            const drawnTitle = document.getElementById('todayDrawnTitle');
            if (drawnBanner && drawnList) {
                drawnBanner.classList.remove('hidden');
                if (clockText) clockText.innerText = `อัปเดต: ${data.thai_now || ''}`;
                const td = data.today_drawn || [];
                drawnTitle.innerText = `📡 ผลหวยวันนี้ (${data.raw_date || data.date}) ออกแล้ว ${td.length} ตลาด`;
                if (td.length > 0) {
                    drawnList.innerHTML = td.map(x => `
                        <span class="px-2 py-0.5 rounded-lg bg-slate-800/90 border border-teal-500/30 text-[10px] text-gray-200">
                            <b>${x.label}</b>: <span class="text-emerald-300 font-bold">${x.top3}</span>|<span class="text-amber-300 font-bold">${x.bot2}</span>
                        </span>
                    `).join('');
                } else {
                    drawnList.innerHTML = `<span class="text-[11px] text-gray-400">⏳ วันนี้ยังไม่มีตลาดที่ออกผล (ตลาดแรก นิเคอิเช้า 09:30 น.)</span>`;
                }
            }

            // Render 2D Top 4 Hot Markets section
            const sec2d = document.getElementById('picks2dSection');
            const cont2d = document.getElementById('picks2dContainer');
            const back2d = document.getElementById('picks2dBackupContainer');
            cont2d.innerHTML = '';
            back2d.innerHTML = '';

            if (data.picks_2d_top4 && data.picks_2d_top4.length > 0 && !data.is_weekend) {
                sec2d.classList.remove('hidden');
                let sum1x = 0, sumAlt = 0, sumBoost = 0;
                data.picks_2d_top4.forEach(it => {
                    sum1x += it.cost_1x;
                    sumAlt += it.cost_alt;
                    sumBoost += it.cost_boost;
                    cont2d.insertAdjacentHTML('beforeend', build2dCardHtml(it, false));
                });
                let bkDrawnCount = 0;
                (data.picks_2d_backup || []).forEach(it => {
                    if (it.actual_top3) bkDrawnCount++;
                    back2d.insertAdjacentHTML('beforeend', build2dCardHtml(it, true));
                });
                const btnBkTxt = document.getElementById('btnToggleBackup2dText');
                if (btnBkTxt) {
                    btnBkTxt.innerText = bkDrawnCount > 0
                        ? `ดูอีก 4 ตลาดสำรอง (ออกผลแล้ว ${bkDrawnCount} ตลาด)`
                        : `ดูอีก 4 ตลาดสำรอง (กรณีต้องการแทงครบ 8 ตลาด)`;
                }
                document.getElementById('picks2dSummaryText').innerHTML = `
                    วันนี้คัด 4 ตลาดฮอต: <b class="text-emerald-300">${data.picks_2d_top4.map(x => x.short_name).join(', ')}</b><br>
                    ทุนรวมวันนี้: คงที่ 1x = <b>${sum1x}฿</b> | สลับ 1x↔2x = <b class="text-emerald-300">${sumAlt}฿</b> | อัดสูตร B 2x = <b class="text-amber-300">${sumBoost}฿</b>
                `;
            } else {
                sec2d.classList.add('hidden');
            }
            
            // Render 3D Cube Sniper section
            const sec3d = document.getElementById('picks3dSection');
            sec3d.classList.remove('hidden');
            const banner = document.getElementById('regimeBanner');
            if (data.use_formula_b) {
                banner.className = 'glass rounded-2xl p-3 border border-purple-500/50 bg-gradient-to-r from-purple-500/20 to-slate-900';
                banner.innerHTML = `
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <span class="px-2 py-0.5 rounded-lg bg-purple-500/30 text-purple-200 font-extrabold text-xs border border-purple-400/40">🔄 3D สูตร B ทำงานอัตโนมัติ</span>
                            <span class="text-xs text-purple-200 font-semibold">โหมดแก้ทางวันที่ 3 (Mid-Cool 5×5×6)</span>
                        </div>
                        <span class="text-[10px] text-purple-300">สถิติเข้า 7/7 (100%)</span>
                    </div>
                `;
            } else {
                banner.className = 'glass rounded-2xl p-3 border border-orange-500/40 bg-gradient-to-r from-orange-500/10 to-slate-900';
                banner.innerHTML = `
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <span class="px-2 py-0.5 rounded-lg bg-orange-500/20 text-orange-300 font-extrabold text-xs border border-orange-500/40">🎯 หวย 3 ตัวบน (สูตร A)</span>
                            <span class="text-xs text-gray-200 font-semibold">3D Cube Sniper (${data.is_weekend ? '4×3×10 = 120 ตัว' : '5×5×6 = 150 ตัว'})</span>
                        </div>
                        <span class="text-[10px] text-gray-400">แพ้สะสมก่อนหน้า: ${data.prev_lose_streak} วัน</span>
                    </div>
                `;
            }

            const container = document.getElementById('picksContainer');
            container.innerHTML = '';
            
            data.picks.forEach((it) => {
                const card = document.createElement('div');
                card.className = 'glass rounded-2xl p-4 border border-darkBorder space-y-3 shadow-lg';
                
                let hPills = it.h_top.map(x => `<span class="px-2 py-0.5 rounded bg-orange-500/20 text-orange-300 font-bold text-xs border border-orange-500/30">${x}</span>`).join(' ');
                let tPills = it.t_top.map(x => `<span class="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold text-xs border border-amber-500/30">${x}</span>`).join(' ');
                let uPills = it.u_top.map(x => `<span class="px-2 py-0.5 rounded bg-yellow-500/20 text-yellow-300 font-bold text-xs border border-yellow-500/30">${x}</span>`).join(' ');
                
                let statusRight = '';
                if (it.actual_top3) {
                    const hitCls3d = it.hit_3d ? 'text-emerald-300 bg-emerald-500/25 border-emerald-500/50' : 'text-rose-300 bg-rose-500/20 border-rose-500/40';
                    const hitTxt3d = it.hit_3d ? '🎯 3D แตก!' : '❌ หลุด';
                    statusRight = `<span class="text-xs font-extrabold ${hitCls3d} border px-2.5 py-0.5 rounded-full">${hitTxt3d} บน:${it.actual_top3}</span>`;
                } else {
                    statusRight = `<span class="text-[10px] font-mono text-orange-400 bg-orange-500/10 border border-orange-500/30 px-2 py-0.5 rounded-full font-bold">⏳ รอผล ${it.draw_time}</span>`;
                }

                card.innerHTML = `
                    <div class="flex items-center justify-between border-b border-darkBorder/50 pb-2">
                        <div>
                            <h3 class="font-extrabold text-base text-white">${it.name}</h3>
                            <p class="text-[11px] text-gray-400">ปิดรับ: <span class="text-orange-400 font-semibold">${it.draw_time}</span></p>
                        </div>
                        ${statusRight}
                    </div>

                    <div class="p-3 rounded-xl bg-gradient-to-br from-orange-500/10 to-slate-900 border border-orange-500/40 space-y-2.5">
                        <div class="flex justify-between items-center">
                            <span class="text-xs font-bold text-orange-300 flex items-center gap-1.5">
                                ${it.formula_label}
                            </span>
                            <span class="text-[10px] font-bold text-orange-300 bg-orange-500/15 px-2 py-0.5 rounded border border-orange-500/30">ทุน ${it.nums_3d_count}฿ จ่าย 850฿</span>
                        </div>
                        <div class="text-[11px] text-gray-300 space-y-1 bg-slate-950/60 p-2 rounded-lg border border-darkBorder/60">
                            <div class="flex items-center gap-1.5 flex-wrap"><span class="text-gray-400 w-10">หลักร้อย:</span> ${hPills}</div>
                            <div class="flex items-center gap-1.5 flex-wrap"><span class="text-gray-400 w-10">หลักสิบ:</span> ${tPills}</div>
                            <div class="flex items-center gap-1.5 flex-wrap"><span class="text-gray-400 w-10">หน่วย:</span> ${uPills}</div>
                        </div>
                        <div class="grid grid-cols-2 gap-2 pt-0.5">
                            <button onclick="copyRaw('${it.nums_3d_comma}', '3 ตัวตรง (${it.nums_3d_count} ตัว) คั่นจุลภาค', '${it.name}')" class="py-2 rounded-xl bg-orange-500/20 hover:bg-orange-500/30 border border-orange-500/40 text-orange-300 text-xs font-bold flex items-center justify-center gap-1.5 active:scale-95 transition">
                                <i class="fa-regular fa-copy"></i> คัดลอก 3 ตัว (${it.nums_3d_count})
                            </button>
                            <button onclick="copyRaw('${it.nums_3d_space}', '3 ตัวตรง (${it.nums_3d_count} ตัว) เว้นวรรค', '${it.name}')" class="py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-600 text-gray-300 text-xs font-semibold flex items-center justify-center gap-1.5 active:scale-95 transition">
                                <i class="fa-solid fa-font"></i> คัดลอก (เว้นวรรค)
                            </button>
                        </div>
                        <div class="pt-1 border-t border-darkBorder/40 flex justify-between items-center text-[10px] text-gray-400">
                            <span>ต้องการสลับคัดลอกอีกสูตรด้วยตัวเอง?</span>
                            <button onclick="copyRaw('${it.nums_3d_alt_comma}', '3 ตัวตรง สูตรสำรอง (${it.nums_3d_alt_count} ตัว)', '${it.name}')" class="text-purple-300 hover:text-purple-200 underline font-semibold">
                                คัดลอก${it.use_formula_b ? 'สูตร A (ปกติ)' : 'สูตร B (แก้ทาง)'} (${it.nums_3d_alt_count} ตัว)
                            </button>
                        </div>
                    </div>
                `;
                container.appendChild(card);
            });

            document.getElementById('picksLoading').classList.add('hidden');
        }

        async function loadPicks() {
            try {
                const res = await fetch('/api/picks?_t=' + Date.now(), { cache: 'no-store' });
                const data = await res.json();
                renderPicksData(data);
            } catch (err) {
                console.error(err);
            }
        }

        function renderChart(historyList) {
            const ctx = document.getElementById('profitChart');
            if (!ctx) return;
            
            // For the chart, only plot days that have at least 1 completed draw so a morning with 0 draws doesn't add a flat tail
            const chartDays = historyList.filter(h => (h.bets_2d_count > 0 || h.draws_count > 0));
            const chronoData = [...chartDays].reverse();
            const labels = chronoData.map(h => h.raw_date);
            
            let cum3d = 0;
            const data3d = chronoData.map(h => { cum3d += getDayModelProfit(h, '3d'); return cum3d; });

            let cum19d = 0;
            const data19d = chronoData.map(h => { cum19d += getDayModelProfit(h, '19d'); return cum19d; });
            
            if (profitChartInstance) {
                profitChartInstance.destroy();
            }

            const datasets = [];
            if (dayGroup === 'wd' && selectedModels['19d']) {
                datasets.push({
                    label: '🔥 2 ตัว (คัด 4 ตลาด/วัน + สูตร B)',
                    data: data19d,
                    borderColor: '#10B981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 2.5,
                    tension: 0.3,
                    pointRadius: 0,
                    pointHitRadius: 10
                });
            }
            if (dayGroup === 'we' || selectedModels['3d']) {
                datasets.push({
                    label: dayGroup === 'we' ? '🌴 3 ตัวบน หวยวันหยุด (เสาร์–อาทิตย์)' : '🎯 3 ตัวบน หวยหุ้น (สูตร A + สลับ B วันที่ 3)',
                    data: data3d,
                    borderColor: '#F59E0B',
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    borderWidth: 2.5,
                    tension: 0.3,
                    pointRadius: 0,
                    pointHitRadius: 10
                });
            }
            
            profitChartInstance = new Chart(ctx, {
                type: 'line',
                data: { labels: labels, datasets: datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: {
                            labels: { color: '#9CA3AF', font: { family: 'Prompt', size: 10 }, boxWidth: 12 }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(15, 23, 42, 0.9)',
                            titleFont: { family: 'Prompt', size: 11 },
                            bodyFont: { family: 'Prompt', size: 11 },
                            padding: 10,
                            cornerRadius: 8,
                            borderColor: '#334155',
                            borderWidth: 1
                        }
                    },
                    scales: {
                        x: {
                            grid: { color: 'rgba(51, 65, 85, 0.3)', drawBorder: false },
                            ticks: { color: '#64748B', font: { family: 'Prompt', size: 9 }, maxTicksLimit: 6 }
                        },
                        y: {
                            grid: { color: 'rgba(51, 65, 85, 0.3)', drawBorder: false },
                            ticks: { color: '#64748B', font: { family: 'Prompt', size: 10 } }
                        }
                    }
                }
            });
        }

        function toggleModelFilter(modelKey) {
            const activeCount = Object.values(selectedModels).filter(Boolean).length;
            if (selectedModels[modelKey] && activeCount <= 1) {
                showToast('แจ้งเตือน', 'ต้องเลือกแสดงอย่างน้อย 1 สูตร');
                return;
            }
            selectedModels[modelKey] = !selectedModels[modelKey];
            updateModelFilterUI();
            if (historyData) {
                renderFilteredHistory();
            }
        }

        function updateModelFilterUI() {
            const config = {
                '19d': { btn: 'btnFilter19d', icon: 'iconFilter19d', active: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40', inactive: 'bg-slate-900/60 text-gray-500 border-slate-700' },
                '3d': { btn: 'btnFilter3d', icon: 'iconFilter3d', active: 'bg-orange-500/20 text-orange-300 border-orange-500/40', inactive: 'bg-slate-900/60 text-gray-500 border-slate-700' }
            };
            
            for (let k in config) {
                const c = config[k];
                const btn = document.getElementById(c.btn);
                const icon = document.getElementById(c.icon);
                if (btn && icon) {
                    if (selectedModels[k]) {
                        btn.className = `py-2 px-2 rounded-xl text-xs font-bold border transition flex items-center justify-center gap-1.5 active:scale-95 ${c.active}`;
                        icon.className = 'fa-solid fa-square-check';
                    } else {
                        btn.className = `py-2 px-2 rounded-xl text-xs font-bold border transition flex items-center justify-center gap-1.5 active:scale-95 ${c.inactive}`;
                        icon.className = 'fa-regular fa-square';
                    }
                }
            }
            
            const names = [];
            if (selectedModels['19d']) names.push('2 ตัว (คัด 4 ตลาด/วัน)');
            if (selectedModels['3d']) names.push('3D Cube Sniper');
            const el = document.getElementById('filterStatusText');
            if (el) el.innerText = names.length === 2 ? 'รวมทั้ง 2 สูตรหลัก' : `เฉพาะ: ${names.join(' + ')}`;
        }

        async function loadHistory() {
            try {
                document.getElementById('historyLoading').classList.remove('hidden');
                document.getElementById('historyContainer').classList.add('hidden');
                
                const res = await fetch('/api/history?_t=' + Date.now(), { cache: 'no-store' });
                const data = await res.json();
                historyData = data;
                
                renderFilteredHistory();
            } catch(e) {
                console.error(e);
            }
        }

        function renderFilteredHistory() {
            if (!historyData) return;
            const data = historyData;
            const st = data.stats;
            
            // Separate weekday (Mon-Fri) and weekend (Sat-Sun) completely
            const groupDaysAll = data.history.filter(h => dayGroup === 'we' ? h.is_weekend : !h.is_weekend);

            let totalProfit3d = 0;
            let totalProfit19d = 0;
            let totalBets19d = 0;
            let totalBets3d = 0;
            let hits3dGroup = 0;
            let draws3dGroup = 0;
            
            groupDaysAll.forEach(h => {
                totalProfit3d += getDayModelProfit(h, '3d');
                totalProfit19d += getDayModelProfit(h, '19d');
                totalBets19d += getDayModelBets(h, '19d');
                totalBets3d += getDayModelBets(h, '3d');
                draws3dGroup += h.draws_count || 0;
                (h.draws || []).forEach(d => { if (!d.is_pending && d.hit_3d) hits3dGroup++; });
            });
            
            let filteredTotalProfit = 0;
            if (dayGroup === 'we') {
                filteredTotalProfit = totalProfit3d;
                const roi3dWe = totalBets3d > 0 ? ((totalProfit3d / totalBets3d) * 100).toFixed(1) : '0.0';
                document.getElementById('cardRoiText').innerText = `3D วันหยุด แตก ${hits3dGroup}/${draws3dGroup} รอบ | ROI: ${totalProfit3d >= 0 ? '+' : ''}${roi3dWe}%`;
            } else {
                if (selectedModels['3d']) filteredTotalProfit += totalProfit3d;
                if (selectedModels['19d']) filteredTotalProfit += totalProfit19d;
                const roi2d = totalBets19d > 0 ? ((totalProfit19d / totalBets19d) * 100).toFixed(1) : '0.0';
                document.getElementById('cardRoiText').innerText = `2D ถูก ${st.total_hits_2d}/${st.total_draws_2d} ไม้ (48.7%) | ROI 2D: +${roi2d}%`;
            }

            document.getElementById('cardProfit3d').innerText = `${totalProfit3d > 0 ? '+' : ''}${totalProfit3d.toLocaleString()} ฿`;
            document.getElementById('cardProfit19d').innerText = `${totalProfit19d > 0 ? '+' : ''}${totalProfit19d.toLocaleString()} ฿`;
            document.getElementById('cardTotalProfitAll').innerText = `${filteredTotalProfit > 0 ? '+' : ''}${filteredTotalProfit.toLocaleString()} ฿`;

            // Filter days in current dayGroup (always include live today so user sees today immediately!)
            const visibleDays = groupDaysAll.filter(h => {
                if (h.is_live_today) return true;
                if (dayGroup === 'we') return getDayModelBets(h, '3d') > 0;
                let b = 0;
                if (selectedModels['19d']) b += getDayModelBets(h, '19d');
                if (selectedModels['3d']) b += getDayModelBets(h, '3d');
                return b > 0;
            });
            document.getElementById('resTotalDays').innerText = `${visibleDays.length} วัน (${dayGroup === 'we' ? 'ส-อา' : 'จ-ศ'})`;

            renderChart(visibleDays);

            // Compute global stats for Tab 3 (Mon-Fri vs Sat-Sun)
            let wdWinDays = 0, wdLossDays = 0;
            let weWinDays = 0, weLossDays = 0;
            let wdProfit = 0, weProfit = 0;
            let wdBets = 0, weBets = 0;
            
            data.history.forEach(h => {
                if (h.is_live_today && h.bets_2d_count === 0 && h.draws_count === 0) return;
                if (h.is_weekend) {
                    const p = getDayModelProfit(h, '3d');
                    const b = getDayModelBets(h, '3d');
                    if (p > 0) weWinDays++;
                    else if (b > 0) weLossDays++;
                    weProfit += p;
                    weBets += b;
                } else {
                    let p = 0, b = 0;
                    if (selectedModels['3d']) { p += getDayModelProfit(h, '3d'); b += getDayModelBets(h, '3d'); }
                    if (selectedModels['19d']) { p += getDayModelProfit(h, '19d'); b += getDayModelBets(h, '19d'); }
                    if (p > 0) wdWinDays++;
                    else if (b > 0) wdLossDays++;
                    wdProfit += p;
                    wdBets += b;
                }
            });

            const updateStat = (id, text) => { if(document.getElementById(id)) document.getElementById(id).innerHTML = text; };
            
            let wdTotal = wdWinDays + wdLossDays;
            let wdWinRate = wdTotal > 0 ? ((wdWinDays / wdTotal) * 100).toFixed(1) : 0;
            let wdRoi = wdBets > 0 ? ((wdProfit / wdBets) * 100).toFixed(1) : 0;
            
            let weTotal = weWinDays + weLossDays;
            let weWinRate = weTotal > 0 ? ((weWinDays / weTotal) * 100).toFixed(1) : 0;
            let weRoi = weBets > 0 ? ((weProfit / weBets) * 100).toFixed(1) : 0;

            updateStat('statWdWinLoss', `ชนะ ${wdWinDays} วัน / แพ้ ${wdLossDays} วัน (${wdWinRate}%)`);
            updateStat('statWdProfit', `<span class="${wdProfit>0?'text-emerald-400':'text-rose-400'}">${wdProfit>0?'+':''}${wdProfit.toLocaleString()} บาท (${wdRoi}% ROI)</span>`);
            
            updateStat('statWeWinLoss', `ชนะ ${weWinDays} วัน / แพ้ ${weLossDays} วัน (${weWinRate}%)`);
            updateStat('statWeProfit', `<span class="${weProfit>0?'text-emerald-400':'text-rose-400'}">${weProfit>0?'+':''}${weProfit.toLocaleString()} บาท (${weRoi}% ROI)</span>`);

            const container = document.getElementById('historyContainer');
            container.innerHTML = '';
            
            const show2d = (dayGroup === 'wd' && selectedModels['19d']);
            const show3d = (dayGroup === 'we' || selectedModels['3d']);

            visibleDays.forEach((h) => {
                const card = document.createElement('div');
                card.className = h.is_live_today
                    ? 'glass rounded-2xl p-3.5 border-2 border-teal-400/70 bg-gradient-to-br from-teal-500/10 to-slate-900 space-y-2.5 shadow-xl'
                    : 'glass rounded-2xl p-3.5 border border-darkBorder space-y-2.5 shadow-md';
                
                let dayProfit = 0;
                let dayBets = 0;
                if (show3d) {
                    dayProfit += getDayModelProfit(h, '3d');
                    dayBets += getDayModelBets(h, '3d');
                }
                if (show2d) {
                    dayProfit += getDayModelProfit(h, '19d');
                    dayBets += getDayModelBets(h, '19d');
                }
                
                let statusBadge = '';
                if (h.is_live_today && h.bets_2d_count === 0 && h.draws_count === 0) {
                    statusBadge = `<span class="px-2.5 py-0.5 rounded-full text-[11px] font-extrabold bg-teal-500/20 text-teal-300 border border-teal-400/40">⏳ รอผลออกวันนี้</span>`;
                } else if (dayProfit > 0) {
                    statusBadge = `<span class="px-2 py-0.5 rounded-full text-[11px] font-extrabold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"><i class="fa-solid fa-check"></i> กำไร +${dayProfit.toLocaleString()} ฿</span>`;
                } else if (dayProfit < 0) {
                    statusBadge = `<span class="px-2 py-0.5 rounded-full text-[11px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30"><i class="fa-solid fa-xmark"></i> ติดลบ ${Math.abs(dayProfit).toLocaleString()} ฿</span>`;
                } else {
                    statusBadge = `<span class="px-2 py-0.5 rounded-full text-[11px] font-bold bg-slate-800 text-gray-400 border border-slate-700">➖ เท่าทุน 0 ฿</span>`;
                }

                let headerBadges = '';
                if (h.is_live_today) {
                    headerBadges += `<span class="px-2 py-0.5 rounded-full bg-teal-500 text-slate-950 text-[10px] font-black ml-1.5">📡 วันนี้ (อัปเดตสด)</span>`;
                }
                if (show2d && (h.bets_2d_count > 0 || h.is_live_today)) {
                    const tot2d = h.is_live_today ? `${h.bets_2d_count}/${h.planned_2d_count || 4}` : `${h.bets_2d_count}`;
                    headerBadges += `<span class="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-[10px] font-bold ml-1.5">2D ถูก ${h.wins_2d}/${tot2d}</span>`;
                    if (h.any_b_2d) {
                        headerBadges += `<span class="px-1.5 py-0.5 rounded bg-purple-500/25 text-purple-200 border border-purple-400/40 text-[10px] font-bold ml-1">🔄 มีสูตร B</span>`;
                    }
                }
                if (show3d && (h.draws_count > 0 || h.is_live_today)) {
                    headerBadges += h.use_b
                        ? `<span class="px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/40 text-[10px] font-bold ml-1.5">🔄 3D ใช้สูตร B (วันที่ 3)</span>`
                        : `<span class="px-1.5 py-0.5 rounded bg-orange-500/15 text-orange-300 border border-orange-500/30 text-[10px] font-bold ml-1.5">🎯 3D ใช้สูตร A</span>`;
                }

                let draws2dHtml = '';
                if (show2d && h.draws_2d && h.draws_2d.length > 0) {
                    draws2dHtml = h.draws_2d.map(d => {
                        let m = d.m_boost;
                        let p = d.pnl_boost;
                        if (playMode === 'all_1x' || playMode === 'sow_1x') { m = d.m_1x; p = d.pnl_1x; }
                        else if (playMode === 'all_alt') { m = d.m_alt; p = d.pnl_alt; }
                        else if (playMode === 'all_2x') { m = d.m_2x; p = d.pnl_2x; }

                        const bTag = d.use_b
                            ? `<span class="px-1.5 py-0.2 rounded bg-purple-500/30 text-purple-200 text-[9px] font-extrabold border border-purple-400/50 ml-1">🔄 สูตร B (วันที่ 3)</span>`
                            : `<span class="px-1.5 py-0.2 rounded bg-emerald-500/15 text-emerald-300 text-[9px] font-bold border border-emerald-500/30 ml-1">สูตร A</span>`;
                        const mTag = m > 1 ? `<span class="px-1.5 py-0.2 rounded bg-amber-500/25 text-amber-300 text-[9px] font-extrabold border border-amber-500/40 ml-1">${m}x</span>` : `<span class="text-gray-400 text-[10px] ml-1">1x</span>`;
                        
                        let hitBadge = '';
                        let resultLine = '';
                        if (d.is_pending) {
                            hitBadge = `<span class="px-2 py-0.5 rounded bg-teal-500/15 text-teal-300 font-bold text-[10px] border border-teal-500/30">⏳ รอผล ${d.draw_time}</span>`;
                            resultLine = `<span>ปิดรับ <b class="text-teal-300">${d.draw_time}</b> (${d.nums_count} ตัว)</span>`;
                        } else {
                            hitBadge = d.hit
                                ? `<span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-extrabold text-[10px] border border-emerald-500/40">✅ เข้า +${p}฿</span>`
                                : `<span class="px-2 py-0.5 rounded bg-slate-800 text-rose-300/90 text-[10px] border border-slate-700">❌ หลุด ${p}฿</span>`;
                            resultLine = `<span>ออก: บน <b class="text-white">${d.actual_top3}</b> | ล่าง <b class="text-white">${d.actual_bot2}</b></span>`;
                        }

                        return `
                            <div class="flex items-center justify-between p-2 rounded-xl bg-slate-900/60 border ${d.use_b ? 'border-purple-500/40' : 'border-darkBorder/50'} text-xs">
                                <div class="min-w-0 flex-1">
                                    <div class="flex items-center flex-wrap">
                                        <span class="font-bold text-white">#${d.rank} ${d.name}</span>
                                        ${bTag}
                                        ${mTag}
                                    </div>
                                    <div class="text-[10px] text-gray-400 flex flex-wrap gap-1.5 mt-0.5">
                                        <span class="text-emerald-300 font-semibold">${d.method_short} (${d.target_thai})</span>
                                        <span>•</span>
                                        ${resultLine}
                                    </div>
                                </div>
                                <div class="text-right shrink-0 pl-2">
                                    ${hitBadge}
                                </div>
                            </div>
                        `;
                    }).join('');
                }

                // If today has backup 2D markets that already drew (like Nikkei Morning at 09:30), display them on Today's live card too!
                let backupDrawnHtml = '';
                if (h.is_live_today && show2d && h.backup_2d_drawn && h.backup_2d_drawn.length > 0) {
                    const bkItems = h.backup_2d_drawn.map(bk => {
                        const badge = bk.hit
                            ? `<span class="text-emerald-300 font-bold">✅ เข้า (บน:${bk.actual_top3}|ล่าง:${bk.actual_bot2})</span>`
                            : `<span class="text-rose-300 font-bold">❌ หลุด (บน:${bk.actual_top3}|ล่าง:${bk.actual_bot2})</span>`;
                        return `<div class="flex justify-between items-center text-[10px] py-0.5"><span class="text-gray-300">สำรอง #${bk.rank} ${bk.name} (${bk.method_short} ${bk.target_thai})</span>${badge}</div>`;
                    }).join('');
                    backupDrawnHtml = `
                        <div class="p-2 rounded-xl bg-slate-950/70 border border-slate-700/70 space-y-1">
                            <p class="text-[10px] font-bold text-teal-300">📌 ผลตลาดสำรองที่ออกแล้ววันนี้ (ไม่ได้อยู่ใน 4 ตลาดตัวจริง):</p>
                            ${bkItems}
                        </div>
                    `;
                }

                let draws3dHtml = '';
                if (show3d && h.draws && h.draws.length > 0) {
                    draws3dHtml = h.draws.map(d => {
                        let f3dBadge = d.use_b
                            ? `<span class="px-1.5 py-0.2 rounded bg-purple-500/30 text-purple-200 text-[9px] font-extrabold border border-purple-400/50 ml-1">🔄 สูตร B</span>`
                            : `<span class="px-1.5 py-0.2 rounded bg-orange-500/15 text-orange-300 text-[9px] font-bold border border-orange-500/30 ml-1">สูตร A</span>`;

                        let hitBadge3d = '';
                        let out3dLine = '';
                        if (d.is_pending) {
                            hitBadge3d = `<span class="px-2 py-0.5 rounded bg-orange-500/15 text-orange-300 font-bold text-[10px] border border-orange-500/30">⏳ รอผล ${d.draw_time || ''}</span>`;
                            out3dLine = `รอผลออกเวลา <b class="text-orange-300">${d.draw_time || '-'}</b> (ทุน ${d.bet_3d}฿)`;
                        } else {
                            let net3dHit = 850 - d.bet_3d;
                            hitBadge3d = d.hit_3d 
                                ? `<span class="px-2 py-0.5 rounded bg-orange-500/20 text-orange-300 font-extrabold text-[10px] border border-orange-500/40">🎯 3D แตก (+${net3dHit}฿)</span>` 
                                : `<span class="px-2 py-0.5 rounded bg-slate-800 text-gray-400 text-[10px] border border-slate-700">❌ 3D หลุด (-${d.bet_3d}฿)</span>`;
                            out3dLine = `ออก: บน <b class="text-white">${d.actual_top3}</b> | ล่าง <b class="text-white">${d.actual_bot2 || '-'}</b>`;
                        }

                        return `
                            <div class="flex items-center justify-between p-2 rounded-xl bg-slate-900/40 border border-orange-500/20 text-xs">
                                <div class="min-w-0 flex-1">
                                    <div class="flex items-center flex-wrap">
                                        <span class="font-bold text-orange-200">${d.name} (3 ตัวบน)</span>
                                        ${f3dBadge}
                                    </div>
                                    <div class="text-[10px] text-gray-400 mt-0.5">
                                        ${out3dLine}
                                    </div>
                                </div>
                                <div class="text-right shrink-0 pl-2">
                                    ${hitBadge3d}
                                </div>
                            </div>
                        `;
                    }).join('');
                }
                
                card.innerHTML = `
                    <div class="flex items-center justify-between border-b border-darkBorder/40 pb-2">
                        <div class="flex items-center flex-wrap">
                            <span class="font-black text-sm text-white">${h.day_name}ที่ ${h.raw_date}</span>
                            ${headerBadges}
                        </div>
                        <div>${statusBadge}</div>
                    </div>
                    <div class="space-y-1.5">
                        ${draws2dHtml}
                        ${backupDrawnHtml}
                        ${draws3dHtml}
                    </div>
                `;
                container.appendChild(card);
            });
            
            document.getElementById('historyLoading').classList.add('hidden');
            document.getElementById('historyContainer').classList.remove('hidden');
        }

        function copyRaw(text, label, mName) {
            navigator.clipboard.writeText(text).then(() => {
                showToast('คัดลอกสำเร็จ!', `คัดลอก ${label} ของ ${mName} แล้ว`);
            });
        }

        async function triggerSync() {
            const icon = document.getElementById('syncIcon');
            icon.classList.add('fa-spin');
            try {
                const res = await fetch('/api/sync?_t=' + Date.now(), { method: 'POST', cache: 'no-store' });
                const data = await res.json();
                showToast('อัปเดตผลสดสำเร็จ!', data.logs.join(' | '));
                if (data.picks_payload) {
                    renderPicksData(data.picks_payload);
                } else {
                    await loadPicks();
                }
                if (data.history_payload) {
                    historyData = data.history_payload;
                    renderFilteredHistory();
                } else {
                    await loadHistory();
                }
            } catch(e) {
                showToast('ข้อผิดพลาด', 'ไม่สามารถดึงผลได้');
            } finally {
                icon.classList.remove('fa-spin');
            }
        }

        function showToast(title, msg) {
            const toast = document.getElementById('toast');
            document.getElementById('toastTitle').innerText = title;
            document.getElementById('toastMsg').innerText = msg;
            toast.classList.remove('-translate-y-24', 'opacity-0');
            toast.classList.add('translate-y-0', 'opacity-100');
            setTimeout(() => {
                toast.classList.add('-translate-y-24', 'opacity-0');
                toast.classList.remove('translate-y-0', 'opacity-100');
            }, 3000);
        }

        window.addEventListener('DOMContentLoaded', loadPicks);
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    local_ip = get_local_ip()
    port = int(os.environ.get("PORT", 5000))
    print("=" * 70)
    print(" [>] STARTING SIMONS QUANT PRO MOBILE APP (2D TOP 4 HOT + 3D SNIPER)")
    print("=" * 70)
    print(f" [*] Mobile Link (Same Wi-Fi) : http://{local_ip}:{port}")
    print(f" [*] Localhost Link           : http://localhost:{port}")
    print("=" * 70)
    app.run(host='0.0.0.0', port=port, debug=False)
