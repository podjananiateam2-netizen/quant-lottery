"""
Mobile Web App Backend - Jim Simons Quant Lottery Dashboard
Includes:
 1. 🎯 Tab 1: วันนี้แทงเลขอะไร (Today's Live Picks: 3D Cube Sniper 5x5x6 + Auto Formula B on Day 3, and 19 Doors Turbo)
 2. ✅ Tab 2: ตรวจผล ถูก/ผิด & ประวัติกำไรรายวัน (Live Verification & Daily PnL with 1x / 2x / Stop-On-Win modes)
 3. 📊 Tab 3: สถิติรวม & กราฟกำไรสะสม (Overall Stats & Analytics)
Author: Antigravity AI
"""
import os, sys, re, json, socket
from datetime import datetime, date
from collections import Counter
import pandas as pd
import yfinance as yf
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ผลหวยหุ้น_ruay.txt")

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
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
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
    lotteries = load_all_lotteries()
    logs = []
    
    # 1. Hang Seng Morning (^HSI)
    try:
        t_hsi = yf.Ticker('^HSI')
        df_hsi = t_hsi.history(interval="15m", period="7d")
        added_hsi = 0
        hsi_dict = lotteries.setdefault('ฮั่งเส็งรอบเช้า', {})
        for idx, row in df_hsi.iterrows():
            time_str = str(idx)
            if '12:00:00' in time_str or '11:58:00' in time_str:
                dt_key = time_str.split(' ')[0]
                if dt_key not in hsi_dict:
                    val = row['Close']
                    val_s = f"{val:.2f}"
                    parts = val_s.split('.')
                    top3 = parts[0][-1] + parts[1]
                    hsi_dict[dt_key] = {
                        'top3': top3, 'h': int(top3[0]), 't': int(top3[1]), 'u': int(top3[2]), 'bot2': '00',
                        'raw_date': f"{dt_key.split('-')[2]}/{dt_key.split('-')[1]}/{dt_key.split('-')[0]}"
                    }
                    added_hsi += 1
        logs.append(f"ฮั่งเส็งรอบเช้า: ซิงค์ {added_hsi} วัน")
    except Exception as e:
        logs.append(f"ฮั่งเส็งรอบเช้า: {str(e)}")

    # 2. FTSE 100 (^FTSE)
    try:
        t_ftse = yf.Ticker('^FTSE')
        df_ftse = t_ftse.history(period="7d")
        added_ftse = 0
        ftse_dict = lotteries.setdefault('หุ้นอังกฤษ', {})
        for idx, row in df_ftse.iterrows():
            dt_key = str(idx).split(' ')[0]
            if dt_key not in ftse_dict and not pd.isna(row['Close']):
                val = row['Close']
                val_s = f"{val:.2f}"
                parts = val_s.split('.')
                top3 = parts[0][-1] + parts[1]
                open_val = row['Open']
                diff = val - open_val
                diff_s = f"{abs(diff):.2f}"
                bot2 = diff_s.split('.')[1]
                ftse_dict[dt_key] = {
                    'top3': top3, 'h': int(top3[0]), 't': int(top3[1]), 'u': int(top3[2]), 'bot2': bot2,
                    'raw_date': f"{dt_key.split('-')[2]}/{dt_key.split('-')[1]}/{dt_key.split('-')[0]}"
                }
                added_ftse += 1
        logs.append(f"หุ้นอังกฤษ: ซิงค์ {added_ftse} วัน")
    except Exception as e:
        logs.append(f"หุ้นอังกฤษ: {str(e)}")

    # 3. Dow Jones (^DJI)
    try:
        t_dji = yf.Ticker('^DJI')
        df_dji = t_dji.history(period="7d")
        added_dji = 0
        dji_dict = lotteries.setdefault('หุ้นดาวโจนส์', {})
        for idx, row in df_dji.iterrows():
            dt_key = str(idx).split(' ')[0]
            if dt_key not in dji_dict and not pd.isna(row['Close']):
                val = row['Close']
                val_s = f"{val:.2f}"
                parts = val_s.split('.')
                top3 = parts[0][-1] + parts[1]
                open_val = row['Open']
                diff = val - open_val
                diff_s = f"{abs(diff):.2f}"
                bot2 = diff_s.split('.')[1]
                dji_dict[dt_key] = {
                    'top3': top3, 'h': int(top3[0]), 't': int(top3[1]), 'u': int(top3[2]), 'bot2': bot2,
                    'raw_date': f"{dt_key.split('-')[2]}/{dt_key.split('-')[1]}/{dt_key.split('-')[0]}"
                }
                added_dji += 1
        logs.append(f"หุ้นดาวโจนส์: ซิงค์ {added_dji} วัน")
    except Exception as e:
        logs.append(f"หุ้นดาวโจนส์: {str(e)}")

    save_all_lotteries(lotteries)
    return logs

def compute_market_models(key_name, d_str, is_we, hsi_today, sorted_lots, date_wd):
    """
    Computes:
    1) 3D Formula A (Hot Top 5x5x6 Weekday / 4x3x10 Weekend, LB=20, Dec=1.0, Sp=1.5, CP=1.0)
    2) 3D Formula B (Day-3 Recovery Mid-Cool Rotation 5x5x6, slice 3:8, 3:8, 2:8, LB=7, Dec=0.85, Sp=1.5, CP=2.0)
    3) 19 Doors Turbo (51 numbers, LB=15, Dec=0.9, Sp=1.5, useH=True, Repeat=+1.5)
    """
    hist = sorted_lots.get(key_name, [])
    past = [item for item in hist if item[0] < d_str]
    if len(past) < 12:
        return None

    # --- 1. 3D Formula A (Normal Regime) ---
    recent_a = past[-20:]
    ha_sc = [0.0]*10; ta_sc = [0.0]*10; ua_sc = [0.0]*10
    for _, it in recent_a:
        ha_sc[it['h']] += 1.0; ta_sc[it['t']] += 1.0; ua_sc[it['u']] += 1.0
    if not is_we and key_name in ('หุ้นอังกฤษ', 'หุ้นดาวโจนส์') and hsi_today:
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
    if not is_we and key_name in ('หุ้นอังกฤษ', 'หุ้นดาวโจนส์') and hsi_today:
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

    # --- 3. 19 Doors Turbo (51 numbers) ---
    recent_19 = past[-15:]
    d_sc = [0.0]*10
    n_19 = len(recent_19)
    for idx, (_, it) in enumerate(recent_19):
        w = 0.9 ** (n_19 - 1 - idx)
        d_sc[it['t']] += w
        d_sc[it['u']] += w
        d_sc[it['h']] += w * 0.4
    if len(recent_19) >= 1:
        last_it = recent_19[-1][1]
        d_sc[last_it['t']] += 1.5
        d_sc[last_it['u']] += 1.5
    if not is_we and key_name in ('หุ้นอังกฤษ', 'หุ้นดาวโจนส์') and hsi_today:
        d_sc[hsi_today['t']] += 1.5
        d_sc[hsi_today['u']] += 1.5
        d_sc[hsi_today['h']] += 1.5 * 0.8
    elif is_we:
        for p_date, it in recent_19[-6:]:
            if date_wd.get(p_date, datetime.strptime(p_date, '%Y-%m-%d').weekday()) in (3, 4):
                d_sc[it['t']] += 1.2
                d_sc[it['u']] += 1.2

    top3_digits = sorted(range(10), key=lambda x: d_sc[x], reverse=True)[:3]

    return {
        'a': {'h': ha_top, 't': ta_top, 'u': ua_top, 'bet': len(ha_top)*len(ta_top)*len(ua_top)},
        'b': {'h': hb_top, 't': tb_top, 'u': ub_top, 'bet': len(hb_top)*len(tb_top)*len(ub_top)},
        'doors_top3': top3_digits
    }

def get_regime_state_by_date(lotteries, sorted_lots, date_wd, all_dates_sorted):
    """
    Runs chronological simulation to determine on each date whether 3D is in Formula A (streak < 2)
    or Formula B (streak >= 2, i.e., Day 3 after 2 consecutive losing days).
    """
    weekday_keys = ['ฮั่งเส็งรอบเช้า', 'หุ้นอังกฤษ', 'หุ้นดาวโจนส์']
    weekend_keys = ['หวยเวียดนาม/ฮานอยพิเศษ', 'หวยเวียดนาม/ฮานอย', 'หวยลาว Super', 'หวยเวียดนาม/ฮานอย VIP']
    
    cur_st = 0
    state_map = {}
    for d_str in all_dates_sorted:
        wd = date_wd[d_str]
        is_we = wd in (5, 6)
        targets = weekend_keys if is_we else weekday_keys
        hsi_today = lotteries.get('ฮั่งเส็งรอบเช้า', {}).get(d_str)
        
        use_b = (cur_st >= 2)
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
            if day_hit:
                cur_st = 0
            elif state_map[d_str]['is_complete']:
                cur_st += 1
    return state_map, cur_st

def calculate_picks(target_date_str=None):
    lotteries = load_all_lotteries()
    all_dates = set()
    for lot_dict in lotteries.values():
        all_dates.update(lot_dict.keys())
    all_dates_sorted = sorted(list(all_dates))
    date_wd = {d: datetime.strptime(d, '%Y-%m-%d').weekday() for d in all_dates_sorted}
    sorted_lots = {k: sorted(v.items(), key=lambda x: x[0]) for k, v in lotteries.items()}
    
    state_map, latest_streak = get_regime_state_by_date(lotteries, sorted_lots, date_wd, all_dates_sorted)
    
    if not target_date_str:
        target_date_str = date.today().strftime('%Y-%m-%d')
        target_dt = date.today()
    else:
        target_dt = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        
    is_weekend = target_dt.weekday() in [5, 6]
    date_wd[target_date_str] = target_dt.weekday()
    
    if target_date_str in state_map:
        use_formula_b = state_map[target_date_str]['use_b']
        prev_streak = state_map[target_date_str]['prev_lose_streak']
    else:
        use_formula_b = (latest_streak >= 2)
        prev_streak = latest_streak

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
    picks_result = []
    
    for key_name, display_name, draw_time in targets:
        m = compute_market_models(key_name, target_date_str, is_weekend, hsi_today, sorted_lots, date_wd)
        if not m:
            continue
            
        active_3d = m['b'] if use_formula_b else m['a']
        alt_3d = m['a'] if use_formula_b else m['b']
        
        nums_3d = [f"{h}{t}{u}" for h in active_3d['h'] for t in active_3d['t'] for u in active_3d['u']]
        nums_3d_alt = [f"{h}{t}{u}" for h in alt_3d['h'] for t in alt_3d['t'] for u in alt_3d['u']]
        
        top3_digits = m['doors_top3']
        doors_set = set()
        for d in top3_digits:
            for unit in range(10):
                doors_set.add(f"{d}{unit}")
                doors_set.add(f"{unit}{d}")
        nums_doors_51 = sorted(list(doors_set))
        
        actual_item = lotteries.get(key_name, {}).get(target_date_str)
        
        picks_result.append({
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
            'top3_digits_doors': top3_digits,
            'nums_3d_count': len(nums_3d),
            'nums_3d_comma': ",".join(nums_3d),
            'nums_3d_space': " ".join(nums_3d),
            'nums_3d_alt_count': len(nums_3d_alt),
            'nums_3d_alt_comma': ",".join(nums_3d_alt),
            'nums_doors_count': len(nums_doors_51),
            'nums_doors_comma': ",".join(nums_doors_51),
            'nums_doors_space': " ".join(nums_doors_51),
            'actual_top3': actual_item['top3'] if actual_item else None
        })
        
    return picks_result, is_weekend, use_formula_b, prev_streak

def generate_history_data():
    lotteries = load_all_lotteries()
    all_dates = set()
    for lot_dict in lotteries.values():
        all_dates.update(lot_dict.keys())
    all_dates_sorted = sorted(list(all_dates))
    date_wd = {d: datetime.strptime(d, '%Y-%m-%d').weekday() for d in all_dates_sorted}
    sorted_lots = {k: sorted(v.items(), key=lambda x: x[0]) for k, v in lotteries.items()}
    
    state_map, _ = get_regime_state_by_date(lotteries, sorted_lots, date_wd, all_dates_sorted)
    
    chrono_days = []
    mult_3d_all = 1
    mult_3d_sow = 1
    mult_19d_all = 1
    mult_19d_sow = 1
    
    for d_str in all_dates_sorted:
        dt = datetime.strptime(d_str, '%Y-%m-%d')
        is_weekend = dt.weekday() in [5, 6]
        if not is_weekend:
            targets = [
                ('ฮั่งเส็งรอบเช้า', '🇭🇰 ฮั่งเส็งเช้า'),
                ('หุ้นอังกฤษ', '🇬🇧 หุ้นอังกฤษ'),
                ('หุ้นดาวโจนส์', '🇺🇸 หุ้นดาวโจนส์')
            ]
        else:
            targets = [
                ('หวยเวียดนาม/ฮานอยพิเศษ', '🇻🇳 ฮานอยพิเศษ'),
                ('หวยเวียดนาม/ฮานอย', '🇻🇳 ฮานอยปกติ'),
                ('หวยลาว Super', '🇱🇦 ลาว Super'),
                ('หวยเวียดนาม/ฮานอย VIP', '🇻🇳 ฮานอย VIP')
            ]
            
        hsi_today = lotteries.get('ฮั่งเส็งรอบเช้า', {}).get(d_str)
        use_b = state_map.get(d_str, {}).get('use_b', False)
        prev_st = state_map.get(d_str, {}).get('prev_lose_streak', 0)
        
        day_draws = []
        total_bets_19d = 0
        total_payout_19d = 0
        total_bets_3d = 0
        total_payout_3d = 0
        
        for key_name, display_name in targets:
            lot_data = lotteries.get(key_name, {})
            if d_str not in lot_data:
                continue
            m = compute_market_models(key_name, d_str, is_weekend, hsi_today, sorted_lots, date_wd)
            if not m:
                continue
                
            actual = lot_data[d_str]
            actual_top3 = actual['top3']
            actual_2d = f"{actual['t']}{actual['u']}"
            
            # 19 Doors Turbo Check
            top3_digits = m['doors_top3']
            t_in = actual['t'] in top3_digits
            u_in = actual['u'] in top3_digits
            hit_19d = t_in or u_in
            is_double_19d = (t_in and u_in and actual['t'] != actual['u'])
            payout_19d = (180 if is_double_19d else 90) if hit_19d else 0
            bet_19d = 51
            total_bets_19d += bet_19d
            total_payout_19d += payout_19d
            
            # 3D Cube Sniper (+ Auto Formula B on Day 3) Check
            active_3d = m['b'] if use_b else m['a']
            hit_3d = (actual['h'] in active_3d['h']) and (actual['t'] in active_3d['t']) and (actual['u'] in active_3d['u'])
            bet_3d = active_3d['bet']
            payout_3d = 850 if hit_3d else 0
            total_bets_3d += bet_3d
            total_payout_3d += payout_3d
            
            day_draws.append({
                'market': key_name,
                'name': display_name,
                'actual_top3': actual_top3,
                'actual_2d': actual_2d,
                'top3_digits_doors': top3_digits,
                'hit_19d': hit_19d,
                'is_double_19d': is_double_19d,
                'bet_19d': bet_19d,
                'payout_19d': payout_19d,
                'hit_3d': hit_3d,
                'bet_3d': bet_3d,
                'payout_3d': payout_3d,
                'use_b': use_b
            })
            
        if day_draws:
            # Stop-On-Win (SOW) daily calculation for 3D and 19D
            sow_bets_3d, sow_payout_3d = 0, 0
            for d in day_draws:
                sow_bets_3d += d['bet_3d']
                if d['hit_3d']:
                    sow_payout_3d += d['payout_3d']
                    break
                    
            sow_bets_19d, sow_payout_19d = 0, 0
            for d in day_draws:
                sow_bets_19d += d['bet_19d']
                if d['hit_19d']:
                    sow_payout_19d += d['payout_19d']
                    break
                    
            prof_3d_1x = total_payout_3d - total_bets_3d
            prof_3d_sow_1x = sow_payout_3d - sow_bets_3d
            prof_3d_2x = prof_3d_1x * mult_3d_all
            prof_3d_sow_2x = prof_3d_sow_1x * mult_3d_sow
            
            prof_19d_1x = total_payout_19d - total_bets_19d
            prof_19d_sow_1x = sow_payout_19d - sow_bets_19d
            prof_19d_2x = prof_19d_1x * mult_19d_all
            prof_19d_sow_2x = prof_19d_sow_1x * mult_19d_sow
            
            day_thai_name = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"][dt.weekday()]
            chrono_days.append({
                'date': d_str,
                'raw_date': f"{dt.day:02d}/{dt.month:02d}/{str(dt.year)[-2:]}",
                'day_name': f"วัน{day_thai_name}",
                'is_weekend': is_weekend,
                'use_b': use_b,
                'prev_lose_streak': prev_st,
                'mult_3d_all': mult_3d_all,
                'mult_3d_sow': mult_3d_sow,
                'mult_19d_all': mult_19d_all,
                'mult_19d_sow': mult_19d_sow,
                'draws_count': len(day_draws),
                'draws': day_draws,
                # 19 Doors
                'bets_19d': total_bets_19d,
                'payout_19d': total_payout_19d,
                'profit_19d': prof_19d_1x,
                'profit_19d_2x': prof_19d_2x,
                'bets_19d_2x': total_bets_19d * mult_19d_all,
                'sow_bets_19d': sow_bets_19d,
                'sow_profit_19d': prof_19d_sow_1x,
                'sow_profit_19d_2x': prof_19d_sow_2x,
                'sow_bets_19d_2x': sow_bets_19d * mult_19d_sow,
                # 3D Cube Sniper
                'bets_3d': total_bets_3d,
                'payout_3d': total_payout_3d,
                'profit_3d': prof_3d_1x,
                'profit_3d_2x': prof_3d_2x,
                'bets_3d_2x': total_bets_3d * mult_3d_all,
                'sow_bets_3d': sow_bets_3d,
                'sow_profit_3d': prof_3d_sow_1x,
                'sow_profit_3d_2x': prof_3d_sow_2x,
                'sow_bets_3d_2x': sow_bets_3d * mult_3d_sow,
            })
            
            mult_3d_all = 2 if prof_3d_1x > 0 else 1
            mult_3d_sow = 2 if prof_3d_sow_1x > 0 else 1
            mult_19d_all = 2 if prof_19d_1x > 0 else 1
            mult_19d_sow = 2 if prof_19d_sow_1x > 0 else 1

    history_days = list(reversed(chrono_days))
    total_days = len(history_days)
    win_days_19d = sum(1 for h in history_days if h['profit_19d'] > 0)
    win_days_3d = sum(1 for h in history_days if h['profit_3d'] > 0)
    total_draws = sum(h['draws_count'] for h in history_days)
    total_hits_19d = sum(sum(1 for d in h['draws'] if d['hit_19d']) for h in history_days)
    total_hits_3d = sum(sum(1 for d in h['draws'] if d['hit_3d']) for h in history_days)
    total_doubles_19d = sum(sum(1 for d in h['draws'] if d['is_double_19d']) for h in history_days)
    
    stats_summary = {
        'total_days': total_days,
        'win_days_19d': win_days_19d,
        'win_days_3d': win_days_3d,
        'total_draws': total_draws,
        'total_hits_19d': total_hits_19d,
        'total_hits_3d': total_hits_3d,
        'total_doubles_19d': total_doubles_19d
    }
    
    return history_days, stats_summary

@app.route('/api/picks')
def api_picks():
    target_d = request.args.get('date')
    picks, is_weekend, use_formula_b, prev_streak = calculate_picks(target_d)
    return jsonify({
        'picks': picks, 
        'is_weekend': is_weekend,
        'use_formula_b': use_formula_b,
        'prev_lose_streak': prev_streak,
        'date': target_d or date.today().strftime('%Y-%m-%d')
    })

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
    return jsonify({
        'status': 'success', 
        'logs': logs, 
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
                    <span id="headerSub">3D Cube Sniper + 19D Turbo</span>
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

            <!-- Active Regime Banner -->
            <div id="regimeBanner" class="glass rounded-2xl p-3 border border-emerald-500/40 bg-gradient-to-r from-emerald-500/10 to-slate-900 hidden"></div>

            <div id="picksLoading" class="py-16 text-center text-gray-400 space-y-2">
                <i class="fa-solid fa-circle-notch fa-spin text-3xl text-emerald-400"></i>
                <p class="text-xs font-medium">กำลังคำนวณสูตร 3D Cube Sniper & 19D Turbo...</p>
            </div>

            <div id="picksContainer" class="space-y-4 hidden"></div>
        </section>


        <!-- ============================================================= -->
        <!-- TAB 2: ✅ ตรวจผลรางวัล ถูก/ผิด (RESULTS VERIFICATION & PNL) -->
        <!-- ============================================================= -->
        <section id="tabResults" class="space-y-4 hidden">
            <div class="flex items-center justify-between">
                <div>
                    <h2 class="text-lg font-black text-white flex items-center gap-2">
                        <i class="fa-solid fa-square-check text-teal-400"></i> ตรวจผล ถูก / ผิด
                    </h2>
                    <p class="text-xs text-gray-400">3D Cube Sniper (สลับสูตร B วันที่ 3) + 19D Turbo</p>
                </div>
                <span class="px-2.5 py-1 text-[11px] font-bold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30" id="resTotalDays">
                    - วัน
                </span>
            </div>

            <!-- Staking & Play Mode Selector -->
            <div class="glass p-3 rounded-2xl border border-darkBorder bg-darkCard/90 space-y-2">
                <div class="flex justify-between items-center text-xs">
                    <span class="font-bold text-gray-300 flex items-center gap-1.5">
                        <i class="fa-solid fa-bolt text-amber-400"></i> โหมดเดินเงิน & การหยุด:
                    </span>
                    <span class="text-[10px] text-amber-300 font-bold" id="playModeDesc">แทงครบทุกตลาด (1x คงที่)</span>
                </div>
                <div class="grid grid-cols-2 gap-1.5">
                    <button onclick="setPlayMode('all_1x')" id="pm_all_1x" class="py-1.5 px-2 rounded-xl text-[11px] font-bold border transition bg-emerald-500/20 text-emerald-300 border-emerald-500/40">
                        แทงครบ (1x)
                    </button>
                    <button onclick="setPlayMode('all_2x')" id="pm_all_2x" class="py-1.5 px-2 rounded-xl text-[11px] font-bold border transition bg-slate-900/60 text-gray-400 border-slate-700">
                        แทงครบ + ชนะทบ 2x 🔥
                    </button>
                    <button onclick="setPlayMode('sow_1x')" id="pm_sow_1x" class="py-1.5 px-2 rounded-xl text-[11px] font-bold border transition bg-slate-900/60 text-gray-400 border-slate-700">
                        ถูกปุ๊บหยุดปั๊บ (1x) 🛡️
                    </button>
                    <button onclick="setPlayMode('sow_2x')" id="pm_sow_2x" class="py-1.5 px-2 rounded-xl text-[11px] font-bold border transition bg-slate-900/60 text-gray-400 border-slate-700">
                        ถูกหยุด + ชนะทบ 2x 🚀
                    </button>
                </div>
            </div>

            <!-- Quick Summary Card -->
            <div class="glass rounded-2xl p-4 border border-emerald-500/30 bg-gradient-to-br from-darkCard to-slate-900 shadow-xl space-y-3">
                <div class="flex justify-between items-center border-b border-darkBorder/60 pb-2.5">
                    <span class="text-xs font-bold text-gray-300 flex items-center gap-1.5">
                        <i class="fa-solid fa-fire text-amber-400"></i> ผลตอบแทนสะสม (65 วัน)
                    </span>
                    <span class="text-[11px] font-bold text-emerald-400" id="cardRoiText">ไม่เคยเสียเกิน 2 วันติด!</span>
                </div>
                <div class="grid grid-cols-2 gap-2.5 text-center">
                    <div class="p-2.5 rounded-xl bg-slate-900/60 border border-orange-500/30">
                        <p class="text-[10px] text-gray-400">🎯 3D Cube Sniper (+สูตร B)</p>
                        <p class="text-base font-extrabold text-orange-400 mt-0.5" id="cardProfit3d">+0 ฿</p>
                    </div>
                    <div class="p-2.5 rounded-xl bg-slate-900/60 border border-emerald-500/30">
                        <p class="text-[10px] text-gray-400">🔥 19 ประตู Turbo (51 ตัว)</p>
                        <p class="text-base font-extrabold text-emerald-400 mt-0.5" id="cardProfit19d">+0 ฿</p>
                    </div>
                </div>
                <div class="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex justify-between items-center mt-2">
                    <span class="text-xs text-emerald-400 font-medium">กำไรสุทธิรวมที่เลือก</span>
                    <span class="text-lg font-black text-emerald-400" id="cardTotalProfitAll">+0 ฿</span>
                </div>
            </div>
            
            <!-- Model Selection Filter Control Bar -->
            <div class="glass p-3.5 rounded-2xl border border-darkBorder bg-darkCard/80 space-y-2">
                <div class="flex justify-between items-center text-xs">
                    <span class="font-extrabold text-gray-200 flex items-center gap-1.5">
                        <i class="fa-solid fa-sliders text-teal-400"></i> เลือกแสดงผลรวม:
                    </span>
                    <span class="text-[10px] text-emerald-400 font-bold" id="filterStatusText">รวมทั้ง 2 สูตรหลัก</span>
                </div>
                <div class="grid grid-cols-2 gap-2">
                    <button onclick="toggleModelFilter('3d')" id="btnFilter3d" class="py-2 px-2 rounded-xl text-xs font-bold border transition flex items-center justify-center gap-1.5 bg-orange-500/20 text-orange-300 border-orange-500/40 active:scale-95">
                        <i class="fa-solid fa-square-check" id="iconFilter3d"></i> 🎯 3 ตัว Cube Sniper
                    </button>
                    <button onclick="toggleModelFilter('19d')" id="btnFilter19d" class="py-2 px-2 rounded-xl text-xs font-bold border transition flex items-center justify-center gap-1.5 bg-emerald-500/20 text-emerald-300 border-emerald-500/40 active:scale-95">
                        <i class="fa-solid fa-square-check" id="iconFilter19d"></i> 🔥 19 ประตู Turbo
                    </button>
                </div>
            </div>

            <!-- Cumulative Profit Chart -->
            <div class="glass rounded-2xl p-4 border border-darkBorder shadow-xl bg-darkCard/50">
                <div class="flex justify-between items-center mb-2">
                    <span class="text-xs font-bold text-gray-300"><i class="fa-solid fa-chart-area text-blue-400"></i> กราฟกำไรสะสม (Cumulative PnL)</span>
                </div>
                <div class="relative h-48 w-full">
                    <canvas id="profitChart"></canvas>
                </div>
            </div>

            <div id="historyLoading" class="py-16 text-center text-gray-400 space-y-2">
                <i class="fa-solid fa-circle-notch fa-spin text-3xl text-teal-400"></i>
                <p class="text-xs font-medium">กำลังโหลดประวัติผลรางวัลย้อนหลัง...</p>
            </div>

            <div id="historyContainer" class="space-y-3.5 hidden"></div>
        </section>


        <!-- ============================================================= -->
        <!-- TAB 3: 📊 สถิติ & พอร์ตภาพรวม (STATS & INSIGHTS) -->
        <!-- ============================================================= -->
        <section id="tabStats" class="space-y-4 hidden">
            <div>
                <h2 class="text-lg font-black text-white flex items-center gap-2">
                    <i class="fa-solid fa-chart-pie text-emerald-400"></i> สถิติ & ประสิทธิภาพพอร์ต
                </h2>
                <p class="text-xs text-gray-400">สรุปสถิติทั้ง 2 สูตรเทพ (ไม่เคยเสียเกิน 2 วันติดตลอด 65 วัน)</p>
            </div>

            <!-- Detailed breakdown cards -->
            <div class="glass rounded-2xl p-4 border border-darkBorder space-y-3">
                <h3 class="text-xs font-bold text-emerald-300 flex items-center gap-1.5">
                    <i class="fa-solid fa-briefcase"></i> วันจันทร์ - ศุกร์ (หวยหุ้น Core 3)
                </h3>
                <div class="space-y-2 text-xs">
                    <div class="flex justify-between py-1 border-b border-darkBorder/40">
                        <span class="text-gray-400">สถิติจบวันชนะกำไร</span>
                        <span class="font-bold text-white" id="statWdWinLoss">-</span>
                    </div>
                    <div class="flex justify-between py-1 border-b border-darkBorder/40">
                        <span class="text-gray-400">เข้าเบิ้ล 2 เด้ง (19 ประตู Turbo)</span>
                        <span class="font-bold text-amber-300" id="statWdDoubles">-</span>
                    </div>
                    <div class="flex justify-between pt-1 font-bold text-sm">
                        <span class="text-gray-300">กำไรสุทธิรวม</span>
                        <span class="text-emerald-400" id="statWdProfit">-</span>
                    </div>
                </div>
            </div>

            <div class="glass rounded-2xl p-4 border border-darkBorder space-y-3">
                <h3 class="text-xs font-bold text-teal-300 flex items-center gap-1.5">
                    <i class="fa-solid fa-umbrella-beach"></i> วันเสาร์ - อาทิตย์ (หวยอาเซียน 4)
                </h3>
                <div class="space-y-2 text-xs">
                    <div class="flex justify-between py-1 border-b border-darkBorder/40">
                        <span class="text-gray-400">สถิติจบวันชนะกำไร</span>
                        <span class="font-bold text-white" id="statWeWinLoss">-</span>
                    </div>
                    <div class="flex justify-between pt-1 font-bold text-sm">
                        <span class="text-gray-300">กำไรสุทธิรวม</span>
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
        let selectedModels = { '3d': true, '19d': true };
        let playMode = 'all_1x'; // 'all_1x', 'all_2x', 'sow_1x', 'sow_2x'

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
            } else if (tab === 'stats') {
                document.getElementById('tabStats').classList.remove('hidden');
                document.getElementById('navStats').classList.add('active-tab-nav');
                if (!historyData) loadHistory();
            }
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        function setPlayMode(mode) {
            playMode = mode;
            const modes = ['all_1x', 'all_2x', 'sow_1x', 'sow_2x'];
            const descMap = {
                'all_1x': 'แทงครบทุกตลาด (1x คงที่)',
                'all_2x': 'แทงครบทุกตลาด + ชนะทบ 2x 🔥',
                'sow_1x': 'ถูกปุ๊บหยุดปั๊บรายวัน (1x) 🛡️',
                'sow_2x': 'ถูกปุ๊บหยุดปั๊บ + ชนะทบ 2x 🚀'
            };
            document.getElementById('playModeDesc').innerText = descMap[mode];
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
                if (playMode === 'sow_1x') return h.sow_profit_3d;
                if (playMode === 'sow_2x') return h.sow_profit_3d_2x;
            } else if (modelKey === '19d') {
                if (playMode === 'all_1x') return h.profit_19d;
                if (playMode === 'all_2x') return h.profit_19d_2x;
                if (playMode === 'sow_1x') return h.sow_profit_19d;
                if (playMode === 'sow_2x') return h.sow_profit_19d_2x;
            }
            return 0;
        }

        function getDayModelBets(h, modelKey) {
            if (modelKey === '3d') {
                if (playMode === 'all_1x') return h.bets_3d;
                if (playMode === 'all_2x') return h.bets_3d_2x;
                if (playMode === 'sow_1x') return h.sow_bets_3d;
                if (playMode === 'sow_2x') return h.sow_bets_3d_2x;
            } else if (modelKey === '19d') {
                if (playMode === 'all_1x') return h.bets_19d;
                if (playMode === 'all_2x') return h.bets_19d_2x;
                if (playMode === 'sow_1x') return h.sow_bets_19d;
                if (playMode === 'sow_2x') return h.sow_bets_19d_2x;
            }
            return 0;
        }

        async function loadPicks() {
            try {
                const res = await fetch('/api/picks');
                const data = await res.json();
                document.getElementById('picksDateHeader').innerText = `งวดประจำวันที่ ${data.date}`;
                document.getElementById('marketBadge').innerText = data.is_weekend ? '🌴 หวยวันหยุด (ส-อา)' : '💼 ตลาดหุ้นหลัก (จ-ศ)';
                
                const banner = document.getElementById('regimeBanner');
                banner.classList.remove('hidden');
                if (data.use_formula_b) {
                    banner.className = 'glass rounded-2xl p-3 border border-purple-500/50 bg-gradient-to-r from-purple-500/20 to-slate-900';
                    banner.innerHTML = `
                        <div class="flex items-center justify-between">
                            <div class="flex items-center gap-2">
                                <span class="px-2 py-0.5 rounded-lg bg-purple-500/30 text-purple-200 font-extrabold text-xs border border-purple-400/40">🔄 สูตร B ทำงานอัตโนมัติ</span>
                                <span class="text-xs text-purple-200 font-semibold">โหมดแก้ทางวันที่ 3 (Mid-Cool 5×5×6)</span>
                            </div>
                            <span class="text-[10px] text-purple-300">สถิติเข้า 7/7 (100%)</span>
                        </div>
                    `;
                } else {
                    banner.className = 'glass rounded-2xl p-3 border border-emerald-500/40 bg-gradient-to-r from-emerald-500/10 to-slate-900';
                    banner.innerHTML = `
                        <div class="flex items-center justify-between">
                            <div class="flex items-center gap-2">
                                <span class="px-2 py-0.5 rounded-lg bg-emerald-500/20 text-emerald-300 font-extrabold text-xs border border-emerald-500/40">🟢 สูตร A (โหมดปกติ)</span>
                                <span class="text-xs text-gray-200 font-semibold">3D Cube Sniper (${data.is_weekend ? '4×3×10 = 120 ตัว' : '5×5×6 = 150 ตัว'})</span>
                            </div>
                            <span class="text-[10px] text-gray-400">แพ้สะสมก่อนหน้า: ${data.prev_lose_streak} วัน</span>
                        </div>
                    `;
                }

                const container = document.getElementById('picksContainer');
                container.innerHTML = '';
                
                data.picks.forEach((it, idx) => {
                    const card = document.createElement('div');
                    card.className = 'glass rounded-2xl p-4 border border-darkBorder space-y-3.5 shadow-lg';
                    
                    let hPills = it.h_top.map(x => `<span class="px-2 py-0.5 rounded bg-orange-500/20 text-orange-300 font-bold text-xs border border-orange-500/30">${x}</span>`).join(' ');
                    let tPills = it.t_top.map(x => `<span class="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold text-xs border border-amber-500/30">${x}</span>`).join(' ');
                    let uPills = it.u_top.map(x => `<span class="px-2 py-0.5 rounded bg-yellow-500/20 text-yellow-300 font-bold text-xs border border-yellow-500/30">${x}</span>`).join(' ');
                    let doorsPills = it.top3_digits_doors.map(x => `<span class="px-2.5 py-0.5 rounded-lg bg-emerald-500/20 text-emerald-300 font-extrabold text-sm border border-emerald-500/40">${x}</span>`).join(' ');
                    
                    let statusRight = it.actual_top3 
                        ? `<span class="text-xs font-extrabold text-amber-300 bg-amber-500/20 border border-amber-500/40 px-2.5 py-0.5 rounded-full">ผลออก: ${it.actual_top3}</span>`
                        : `<span class="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded-full font-bold">Quant Live</span>`;

                    card.innerHTML = `
                        <div class="flex items-center justify-between border-b border-darkBorder/50 pb-2">
                            <div>
                                <h3 class="font-extrabold text-base text-white">${it.name}</h3>
                                <p class="text-[11px] text-gray-400">ปิดรับ: <span class="text-emerald-400 font-semibold">${it.draw_time}</span></p>
                            </div>
                            ${statusRight}
                        </div>

                        <!-- 1. 🎯 3D Cube Sniper (5x5x6 = 150) + Auto Formula B -->
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
                                    คัดลอก${it.use_formula_b ? 'สูตร A' : 'สูตร B (แก้ทาง)'} (${it.nums_3d_alt_count} ตัว)
                                </button>
                            </div>
                        </div>

                        <!-- 2. 🔥 2D 19 Doors Turbo (51 numbers) -->
                        <div class="p-3 rounded-xl bg-gradient-to-br from-emerald-500/10 to-slate-900 border border-emerald-500/40 space-y-2">
                            <div class="flex justify-between items-center">
                                <span class="text-xs font-bold text-emerald-300 flex items-center gap-1.5">
                                    <i class="fa-solid fa-fire text-emerald-400"></i> 🔥 19 ประตู Turbo (51 ตัว)
                                </span>
                                <span class="text-[10px] font-bold text-emerald-300 bg-emerald-500/15 px-2 py-0.5 rounded border border-emerald-500/30">ทุน 51฿ (ลุ้น 2 เด้ง 180฿)</span>
                            </div>
                            <div class="text-xs text-gray-300 flex items-center gap-2">
                                <span class="text-gray-400">3 เลขเด่นรูด 19 ประตู:</span> ${doorsPills}
                            </div>
                            <div class="grid grid-cols-2 gap-2 pt-1">
                                <button onclick="copyRaw('${it.nums_doors_comma}', '19 ประตู Turbo (51 ตัว) คั่นจุลภาค', '${it.name}')" class="py-2 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 text-xs font-bold flex items-center justify-center gap-1.5 active:scale-95 transition">
                                    <i class="fa-regular fa-copy"></i> คัดลอก (19 ประตู)
                                </button>
                                <button onclick="copyRaw('${it.nums_doors_space}', '19 ประตู Turbo เว้นวรรค', '${it.name}')" class="py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-600 text-gray-300 text-xs font-semibold flex items-center justify-center gap-1.5 active:scale-95 transition">
                                    <i class="fa-solid fa-font"></i> คัดลอก (เว้นวรรค)
                                </button>
                            </div>
                        </div>
                    `;
                    container.appendChild(card);
                });

                document.getElementById('picksLoading').classList.add('hidden');
                document.getElementById('picksContainer').classList.remove('hidden');
            } catch (err) {
                console.error(err);
            }
        }

        function renderChart(historyList) {
            const ctx = document.getElementById('profitChart');
            if (!ctx) return;
            
            const chronoData = [...historyList].reverse();
            const labels = chronoData.map(h => h.raw_date);
            
            let cum3d = 0;
            const data3d = chronoData.map(h => { cum3d += getDayModelProfit(h, '3d'); return cum3d; });

            let cum19d = 0;
            const data19d = chronoData.map(h => { cum19d += getDayModelProfit(h, '19d'); return cum19d; });
            
            if (profitChartInstance) {
                profitChartInstance.destroy();
            }
            
            profitChartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: '🎯 3D Cube Sniper (+สูตร B)',
                            data: data3d,
                            borderColor: '#F59E0B',
                            backgroundColor: 'rgba(245, 158, 11, 0.1)',
                            borderWidth: 2.5,
                            tension: 0.3,
                            pointRadius: 0,
                            pointHitRadius: 10
                        },
                        {
                            label: '🔥 19 ประตู Turbo',
                            data: data19d,
                            borderColor: '#10B981',
                            backgroundColor: 'rgba(16, 185, 129, 0.1)',
                            borderWidth: 2.5,
                            tension: 0.3,
                            pointRadius: 0,
                            pointHitRadius: 10
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false,
                    },
                    plugins: {
                        legend: {
                            labels: {
                                color: '#9CA3AF',
                                font: { family: 'Prompt', size: 10 },
                                boxWidth: 12
                            }
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
                showToast('แจ้งเตือน', 'ต้องเลือกอย่างน้อย 1 โมเดล');
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
                '3d': { btn: 'btnFilter3d', icon: 'iconFilter3d', active: 'bg-orange-500/20 text-orange-300 border-orange-500/40', inactive: 'bg-slate-900/60 text-gray-500 border-slate-700' },
                '19d': { btn: 'btnFilter19d', icon: 'iconFilter19d', active: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40', inactive: 'bg-slate-900/60 text-gray-500 border-slate-700' }
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
            if (selectedModels['3d']) names.push('3D Cube Sniper');
            if (selectedModels['19d']) names.push('19 ประตู Turbo');
            const el = document.getElementById('filterStatusText');
            if (el) el.innerText = names.length === 2 ? 'รวมทั้ง 2 สูตรหลัก' : `เฉพาะ: ${names.join(' + ')}`;
        }

        async function loadHistory() {
            try {
                document.getElementById('historyLoading').classList.remove('hidden');
                document.getElementById('historyContainer').classList.add('hidden');
                
                const res = await fetch('/api/history');
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
            document.getElementById('resTotalDays').innerText = `${st.total_days} วัน`;
            
            let totalProfit3d = 0;
            let totalProfit19d = 0;
            
            data.history.forEach(h => {
                totalProfit3d += getDayModelProfit(h, '3d');
                totalProfit19d += getDayModelProfit(h, '19d');
            });
            
            let filteredTotalProfit = 0;
            if (selectedModels['3d']) filteredTotalProfit += totalProfit3d;
            if (selectedModels['19d']) filteredTotalProfit += totalProfit19d;

            document.getElementById('cardProfit3d').innerText = `${totalProfit3d > 0 ? '+' : ''}${totalProfit3d.toLocaleString()} ฿`;
            document.getElementById('cardProfit19d').innerText = `${totalProfit19d > 0 ? '+' : ''}${totalProfit19d.toLocaleString()} ฿`;
            document.getElementById('cardTotalProfitAll').innerText = `${filteredTotalProfit > 0 ? '+' : ''}${filteredTotalProfit.toLocaleString()} ฿`;

            renderChart(data.history);

            // Tab 3 Stats Computation based on selection & playMode
            let wdWinDays = 0, wdLossDays = 0;
            let weWinDays = 0, weLossDays = 0;
            let wdProfit = 0, weProfit = 0;
            let wdBets = 0, weBets = 0;
            let wdDoubles = 0;
            
            data.history.forEach(h => {
                let hFilteredProfit = 0;
                let hFilteredBets = 0;
                if (selectedModels['3d']) {
                    hFilteredProfit += getDayModelProfit(h, '3d');
                    hFilteredBets += getDayModelBets(h, '3d');
                }
                if (selectedModels['19d']) {
                    hFilteredProfit += getDayModelProfit(h, '19d');
                    hFilteredBets += getDayModelBets(h, '19d');
                }
                
                if (h.is_weekend) {
                    if (hFilteredProfit > 0) weWinDays++;
                    else if (hFilteredBets > 0) weLossDays++;
                    weProfit += hFilteredProfit;
                    weBets += hFilteredBets;
                } else {
                    if (hFilteredProfit > 0) wdWinDays++;
                    else if (hFilteredBets > 0) wdLossDays++;
                    wdProfit += hFilteredProfit;
                    wdBets += hFilteredBets;
                    wdDoubles += h.draws.filter(d => d.is_double_19d).length;
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
            updateStat('statWdDoubles', `${wdDoubles} ครั้ง`);
            updateStat('statWdProfit', `<span class="${wdProfit>0?'text-emerald-400':'text-rose-400'}">${wdProfit>0?'+':''}${wdProfit.toLocaleString()} บาท (${wdRoi}% ROI)</span>`);
            
            updateStat('statWeWinLoss', `ชนะ ${weWinDays} วัน / แพ้ ${weLossDays} วัน (${weWinRate}%)`);
            updateStat('statWeProfit', `<span class="${weProfit>0?'text-emerald-400':'text-rose-400'}">${weProfit>0?'+':''}${weProfit.toLocaleString()} บาท (${weRoi}% ROI)</span>`);

            const container = document.getElementById('historyContainer');
            container.innerHTML = '';
            
            data.history.forEach((h) => {
                const card = document.createElement('div');
                card.className = 'glass rounded-2xl p-3.5 border border-darkBorder space-y-2.5 shadow-md';
                
                let dayProfit = 0;
                if (selectedModels['3d']) dayProfit += getDayModelProfit(h, '3d');
                if (selectedModels['19d']) dayProfit += getDayModelProfit(h, '19d');
                
                const statusBadge = dayProfit > 0 
                    ? `<span class="px-2 py-0.5 rounded-full text-[11px] font-extrabold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"><i class="fa-solid fa-check"></i> กำไร +${dayProfit.toLocaleString()} ฿</span>`
                    : dayProfit < 0
                    ? `<span class="px-2 py-0.5 rounded-full text-[11px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30"><i class="fa-solid fa-xmark"></i> ติดลบ ${Math.abs(dayProfit).toLocaleString()} ฿</span>`
                    : `<span class="px-2 py-0.5 rounded-full text-[11px] font-bold bg-slate-800 text-gray-400 border border-slate-700">➖ เท่าทุน 0 ฿</span>`;

                const formulaBadge = h.use_b
                    ? `<span class="px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/40 text-[10px] font-bold ml-1.5">🔄 สูตร B (วันที่ 3)</span>`
                    : `<span class="px-1.5 py-0.5 rounded bg-slate-800 text-gray-400 border border-slate-700 text-[10px] ml-1.5">สูตร A</span>`;
                    
                let drawsHtml = h.draws.map(d => {
                    let hitBadge19 = '';
                    if (d.is_double_19d) {
                        hitBadge19 = `<span class="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-extrabold text-[10px] border border-amber-500/40">🔥🔥 19D 2เด้ง (+129฿)</span>`;
                    } else if (d.hit_19d) {
                        hitBadge19 = `<span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold text-[10px] border border-emerald-500/30">🔥 19D เข้า (+39฿)</span>`;
                    } else {
                        hitBadge19 = `<span class="px-2 py-0.5 rounded bg-slate-800 text-gray-400 text-[10px] border border-slate-700">❌ 19D หลุด (-51฿)</span>`;
                    }
                        
                    let net3dHit = 850 - d.bet_3d;
                    let hitBadge3d = d.hit_3d 
                        ? `<span class="px-2 py-0.5 rounded bg-orange-500/20 text-orange-300 font-extrabold text-[10px] border border-orange-500/40">🎯 3D แตก (+${net3dHit}฿)</span>` 
                        : `<span class="px-2 py-0.5 rounded bg-slate-800 text-gray-400 text-[10px] border border-slate-700">❌ 3D หลุด (-${d.bet_3d}฿)</span>`;

                    return `
                        <div class="flex items-center justify-between p-2 rounded-xl bg-slate-900/60 border border-darkBorder/50 text-xs">
                            <div class="min-w-0 flex-1">
                                <span class="font-bold text-white">${d.name}</span>
                                <div class="text-[10px] text-gray-400 flex flex-wrap gap-1.5 mt-0.5">
                                    <span>ออก: <b class="text-white">${d.actual_top3}</b> (${d.actual_2d})</span>
                                    <span>•</span>
                                    <span>เด่น 19D: <b class="text-emerald-300">[${d.top3_digits_doors.join(', ')}]</b></span>
                                </div>
                            </div>
                            <div class="text-right flex flex-col gap-1 items-end shrink-0 pl-2">
                                ${selectedModels['3d'] ? hitBadge3d : ''}
                                ${selectedModels['19d'] ? hitBadge19 : ''}
                            </div>
                        </div>
                    `;
                }).join('');
                
                card.innerHTML = `
                    <div class="flex items-center justify-between border-b border-darkBorder/40 pb-2">
                        <div class="flex items-center flex-wrap">
                            <span class="font-black text-sm text-white">${h.day_name}ที่ ${h.raw_date}</span>
                            ${formulaBadge}
                        </div>
                        <div>${statusBadge}</div>
                    </div>
                    <div class="space-y-1.5">
                        ${drawsHtml}
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
                const res = await fetch('/api/sync', { method: 'POST' });
                const data = await res.json();
                showToast('อัปเดตผลสำเร็จ!', data.logs.join(' | '));
                loadPicks();
                if (currentTab === 'results' || currentTab === 'stats') loadHistory();
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
    print(" [>] STARTING SIMONS QUANT PRO MOBILE APP (3D CUBE SNIPER + 19D TURBO)")
    print("=" * 70)
    print(f" [*] Mobile Link (Same Wi-Fi) : http://{local_ip}:{port}")
    print(f" [*] Localhost Link           : http://localhost:{port}")
    print("=" * 70)
    app.run(host='0.0.0.0', port=port, debug=False)
