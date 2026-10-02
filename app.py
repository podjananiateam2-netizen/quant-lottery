"""
Mobile Web App Backend - Jim Simons Quant Lottery Dashboard
Includes:
 1. 🎯 Tab 1: วันนี้แทงเลขอะไร (Today's Live Picks with 1-Click Copy)
 2. ✅ Tab 2: ตรวจผล ถูก/ผิด & ประวัติกำไรรายวัน (Live Verification & Daily PnL)
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
        
        # Fallback to 15m intraday if latest day missing
        df_ftse_15m = t_ftse.history(interval="15m", period="7d")
        for idx, row in df_ftse_15m.iterrows():
            time_str = str(idx)
            if '16:00:00' in time_str or '16:15:00' in time_str or '16:30:00' in time_str:
                dt_key = time_str.split(' ')[0]
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

def calculate_picks(target_date_str=None):
    lotteries = load_all_lotteries()
    if not target_date_str:
        target_date_str = date.today().strftime('%Y-%m-%d')
        target_dt = date.today()
    else:
        target_dt = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        
    is_weekend = target_dt.weekday() in [5, 6]
    picks_result = []
    
    if not is_weekend:
        targets = [
            ('ฮั่งเส็งรอบเช้า', '🇭🇰 ฮั่งเส็งเช้า', '11:00 น.'),
            ('หุ้นอังกฤษ', '🇬🇧 หุ้นอังกฤษ', '23:30 น.'),
            ('หุ้นดาวโจนส์', '🇺🇸 หุ้นดาวโจนส์', '03:30 น.')
        ]
        hsi_today = lotteries.get('ฮั่งเส็งรอบเช้า', {}).get(target_date_str)
        
        for key_name, display_name, draw_time in targets:
            lot_data = lotteries.get(key_name, {})
            past_records = [{'date': d, 'h': l['h'], 't': l['t'], 'u': l['u'], 'top3': l['top3']} for d, l in lot_data.items() if d < target_date_str]
            if len(past_records) < 10:
                continue
            df_past = pd.DataFrame(past_records).sort_values('date').reset_index(drop=True)
            
            past_20 = df_past.tail(20)
            h_scores = Counter(past_20['h'])
            t_scores = Counter(past_20['t'])
            u_scores = Counter(past_20['u'])
            
            spillover_active = False
            if key_name in ['หุ้นอังกฤษ', 'หุ้นดาวโจนส์'] and hsi_today:
                h_scores[hsi_today['h']] += 1.5
                t_scores[hsi_today['t']] += 1.5
                u_scores[hsi_today['u']] += 1.5
                spillover_active = True
                
            # 1. 3D Top 4x3 Grid (120 numbers)
            h_top = [x[0] for x in h_scores.most_common(4)]
            t_top3 = [x[0] for x in t_scores.most_common(3)]
            nums_3d_120 = [f"{h}{t}{u}" for h in h_top for t in t_top3 for u in range(10)]
            
            # 2. 2D Top 5x6 Grid Matrix (30 numbers)
            t_top5 = [x[0] for x in t_scores.most_common(5)]
            u_top6 = [x[0] for x in u_scores.most_common(6)]
            nums_2d_30 = [f"{t}{u}" for t in t_top5 for u in u_top6]
            
            # 3. 2D 19 Doors Top 3 Digits (51 numbers)
            all_digits = list(past_20['t']) + list(past_20['u'])
            d_cnt = Counter(all_digits)
            if spillover_active and hsi_today:
                d_cnt[hsi_today['t']] += 1.5
                d_cnt[hsi_today['u']] += 1.5
            top3_digits = [x[0] for x in d_cnt.most_common(3)]
            
            doors_set = set()
            for d in top3_digits:
                for unit in range(10):
                    doors_set.add(f"{d}{unit}")
                    doors_set.add(f"{unit}{d}")
            nums_doors_51 = sorted(list(doors_set))
            
            picks_result.append({
                'lottery_key': key_name,
                'name': display_name,
                'draw_time': draw_time,
                'h_top': h_top,
                't_top': t_top3,
                'u_top': u_top6,
                'top3_digits_doors': top3_digits,
                'nums_3d_count': len(nums_3d_120),
                'nums_3d_comma': ",".join(nums_3d_120),
                'nums_3d_space': " ".join(nums_3d_120),
                'nums_2d_count': len(nums_2d_30),
                'nums_2d_comma': ",".join(nums_2d_30),
                'nums_2d_space': " ".join(nums_2d_30),
                'nums_doors_count': len(nums_doors_51),
                'nums_doors_comma': ",".join(nums_doors_51),
                'nums_doors_space': " ".join(nums_doors_51)
            })
    else:
        targets = [
            ('หวยเวียดนาม/ฮานอยพิเศษ', '🇻🇳 ฮานอยพิเศษ', '17:30 น.'),
            ('หวยเวียดนาม/ฮานอย', '🇻🇳 ฮานอยปกติ', '18:30 น.'),
            ('หวยลาว Super', '🇱🇦 ลาว Super', '19:00 น.'),
            ('หวยเวียดนาม/ฮานอย VIP', '🇻🇳 ฮานอย VIP', '19:30 น.')
        ]
        for key_name, display_name, draw_time in targets:
            lot_data = lotteries.get(key_name, {})
            past_records = [{'date': d, 'h': l['h'], 't': l['t'], 'u': l['u'], 'top3': l['top3']} for d, l in lot_data.items() if d < target_date_str]
            if len(past_records) < 10:
                continue
            df_past = pd.DataFrame(past_records).sort_values('date').reset_index(drop=True)
            
            p15 = df_past.tail(15)
            h_cnt = Counter(p15['h'])
            t_cnt = Counter(p15['t'])
            u_cnt = Counter(p15['u'])
            
            past_tf = df_past[pd.to_datetime(df_past['date']).dt.weekday.isin([3, 4])].tail(2)
            for _, r_tf in past_tf.iterrows():
                h_cnt[r_tf['h']] += 1.5
                t_cnt[r_tf['t']] += 1.5
                u_cnt[r_tf['u']] += 1.5
                
            h_top = [x[0] for x in h_cnt.most_common(4)]
            t_top3 = [x[0] for x in t_cnt.most_common(3)]
            nums_3d_120 = [f"{h}{t}{u}" for h in h_top for t in t_top3 for u in range(10)]
            
            t_top5 = [x[0] for x in t_cnt.most_common(5)]
            u_top6 = [x[0] for x in u_cnt.most_common(6)]
            nums_2d_30 = [f"{t}{u}" for t in t_top5 for u in u_top6]
            
            all_digits = list(p15['t']) + list(p15['u'])
            d_cnt = Counter(all_digits)
            for _, r_tf in past_tf.iterrows():
                d_cnt[r_tf['t']] += 1.5
                d_cnt[r_tf['u']] += 1.5
            top3_digits = [x[0] for x in d_cnt.most_common(3)]
            
            doors_set = set()
            for d in top3_digits:
                for unit in range(10):
                    doors_set.add(f"{d}{unit}")
                    doors_set.add(f"{unit}{d}")
            nums_doors_51 = sorted(list(doors_set))
            
            picks_result.append({
                'lottery_key': key_name,
                'name': display_name,
                'draw_time': draw_time,
                'h_top': h_top,
                't_top': t_top3,
                'u_top': u_top6,
                'top3_digits_doors': top3_digits,
                'nums_3d_count': len(nums_3d_120),
                'nums_3d_comma': ",".join(nums_3d_120),
                'nums_3d_space': " ".join(nums_3d_120),
                'nums_2d_count': len(nums_2d_30),
                'nums_2d_comma': ",".join(nums_2d_30),
                'nums_2d_space': " ".join(nums_2d_30),
                'nums_doors_count': len(nums_doors_51),
                'nums_doors_comma': ",".join(nums_doors_51),
                'nums_doors_space': " ".join(nums_doors_51)
            })
            
    return picks_result, is_weekend

def generate_history_data():
    lotteries = load_all_lotteries()
    all_dates = set()
    for lot_dict in lotteries.values():
        all_dates.update(lot_dict.keys())
    all_dates = sorted(list(all_dates), reverse=True)
    
    history_days = []
    
    for d_str in all_dates:
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
            
        day_draws = []
        total_bets_19d = 0
        total_payout_19d = 0
        total_bets_2d = 0
        total_payout_2d = 0
        total_bets_3d = 0
        total_payout_3d = 0
        
        hsi_today = lotteries.get('ฮั่งเส็งรอบเช้า', {}).get(d_str)
        
        for key_name, display_name in targets:
            lot_data = lotteries.get(key_name, {})
            if d_str not in lot_data:
                continue
            actual = lot_data[d_str]
            actual_top3 = actual['top3']
            actual_2d = f"{actual['t']}{actual['u']}"
            
            past_records = [{'date': k, 'h': v['h'], 't': v['t'], 'u': v['u'], 'top3': v['top3']} for k, v in lot_data.items() if k < d_str]
            if len(past_records) < 10:
                continue
            df_past = pd.DataFrame(past_records).sort_values('date').reset_index(drop=True)
            
            if not is_weekend:
                past_20 = df_past.tail(20)
                h_scores = Counter(past_20['h'])
                t_scores = Counter(past_20['t'])
                u_scores = Counter(past_20['u'])
                
                spillover_active = False
                if key_name in ['หุ้นอังกฤษ', 'หุ้นดาวโจนส์'] and hsi_today:
                    h_scores[hsi_today['h']] += 1.5
                    t_scores[hsi_today['t']] += 1.5
                    u_scores[hsi_today['u']] += 1.5
                    spillover_active = True
                    
                h_top = [x[0] for x in h_scores.most_common(4)]
                t_top3 = [x[0] for x in t_scores.most_common(3)]
                nums_3d_120 = [f"{h}{t}{u}" for h in h_top for t in t_top3 for u in range(10)]
                
                t_top5 = [x[0] for x in t_scores.most_common(5)]
                u_top6 = [x[0] for x in u_scores.most_common(6)]
                nums_2d_30 = [f"{t}{u}" for t in t_top5 for u in u_top6]
                
                all_digits = list(past_20['t']) + list(past_20['u'])
                d_cnt = Counter(all_digits)
                if spillover_active and hsi_today:
                    d_cnt[hsi_today['t']] += 1.5
                    d_cnt[hsi_today['u']] += 1.5
                top3_digits = [x[0] for x in d_cnt.most_common(3)]
            else:
                p15 = df_past.tail(15)
                h_cnt = Counter(p15['h'])
                t_cnt = Counter(p15['t'])
                u_cnt = Counter(p15['u'])
                past_tf = df_past[pd.to_datetime(df_past['date']).dt.weekday.isin([3, 4])].tail(2)
                for _, r_tf in past_tf.iterrows():
                    h_cnt[r_tf['h']] += 1.5
                    t_cnt[r_tf['t']] += 1.5
                    u_cnt[r_tf['u']] += 1.5
                h_top = [x[0] for x in h_cnt.most_common(4)]
                t_top3 = [x[0] for x in t_cnt.most_common(3)]
                nums_3d_120 = [f"{h}{t}{u}" for h in h_top for t in t_top3 for u in range(10)]
                t_top5 = [x[0] for x in t_cnt.most_common(5)]
                u_top6 = [x[0] for x in u_cnt.most_common(6)]
                nums_2d_30 = [f"{t}{u}" for t in t_top5 for u in u_top6]
                all_digits = list(p15['t']) + list(p15['u'])
                d_cnt = Counter(all_digits)
                for _, r_tf in past_tf.iterrows():
                    d_cnt[r_tf['t']] += 1.5
                    d_cnt[r_tf['u']] += 1.5
                top3_digits = [x[0] for x in d_cnt.most_common(3)]

            # 19 Doors Check
            doors_set = set()
            for digit in top3_digits:
                for unit in range(10):
                    doors_set.add(f"{digit}{unit}")
                    doors_set.add(f"{unit}{digit}")
            
            hit_19d = actual_2d in doors_set
            t_in = actual['t'] in top3_digits
            u_in = actual['u'] in top3_digits
            is_double_19d = (t_in and u_in)
            
            payout_19d = 180 if is_double_19d else (90 if hit_19d else 0)
            total_bets_19d += 51
            total_payout_19d += payout_19d
            
            # 2D Matrix 30 Check
            hit_2d = actual_2d in nums_2d_30
            payout_2d = 90 if hit_2d else 0
            total_bets_2d += 30
            total_payout_2d += payout_2d
            
            # 3D 120 Check
            hit_3d = actual_top3 in nums_3d_120
            payout_3d = 850 if hit_3d else 0
            total_bets_3d += 120
            total_payout_3d += payout_3d
            
            day_draws.append({
                'market': key_name,
                'name': display_name,
                'actual_top3': actual_top3,
                'actual_2d': actual_2d,
                'top3_digits_doors': top3_digits,
                'hit_19d': hit_19d,
                'is_double_19d': is_double_19d,
                'payout_19d': payout_19d,
                'hit_2d': hit_2d,
                'payout_2d': payout_2d,
                'hit_3d': hit_3d,
                'payout_3d': payout_3d
            })
            
        if day_draws:
            day_thai_name = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"][dt.weekday()]
            history_days.append({
                'date': d_str,
                'raw_date': f"{dt.day:02d}/{dt.month:02d}/{str(dt.year)[-2:]}",
                'day_name': f"วัน{day_thai_name}",
                'is_weekend': is_weekend,
                'draws_count': len(day_draws),
                'draws': day_draws,
                # 19 Doors Totals
                'bets_19d': total_bets_19d,
                'payout_19d': total_payout_19d,
                'profit_19d': total_payout_19d - total_bets_19d,
                'is_win_19d': (total_payout_19d - total_bets_19d) > 0,
                # 2D Matrix Totals
                'bets_2d': total_bets_2d,
                'payout_2d': total_payout_2d,
                'profit_2d': total_payout_2d - total_bets_2d,
                # 3D Totals
                'bets_3d': total_bets_3d,
                'payout_3d': total_payout_3d,
                'profit_3d': total_payout_3d - total_bets_3d
            })
            
    # Calculate aggregate stats
    total_days = len(history_days)
    win_days_19d = sum(1 for h in history_days if h['profit_19d'] > 0)
    total_draws = sum(h['draws_count'] for h in history_days)
    total_hits_19d = sum(sum(1 for d in h['draws'] if d['hit_19d']) for h in history_days)
    total_doubles_19d = sum(sum(1 for d in h['draws'] if d['is_double_19d']) for h in history_days)
    total_bets_all_19d = sum(h['bets_19d'] for h in history_days)
    total_payout_all_19d = sum(h['payout_19d'] for h in history_days)
    total_profit_all_19d = total_payout_all_19d - total_bets_all_19d
    roi_19d = (total_profit_all_19d / total_bets_all_19d * 100) if total_bets_all_19d > 0 else 0
    
    stats_summary = {
        'total_days': total_days,
        'win_days_19d': win_days_19d,
        'day_win_rate_19d': round(win_days_19d / total_days * 100, 1) if total_days > 0 else 0,
        'total_draws': total_draws,
        'total_hits_19d': total_hits_19d,
        'hit_rate_19d': round(total_hits_19d / total_draws * 100, 1) if total_draws > 0 else 0,
        'total_doubles_19d': total_doubles_19d,
        'total_bets_19d': total_bets_all_19d,
        'total_payout_19d': total_payout_all_19d,
        'total_profit_19d': total_profit_all_19d,
        'roi_19d': round(roi_19d, 1)
    }
    
    return history_days, stats_summary

@app.route('/api/picks')
def api_picks():
    target_d = request.args.get('date')
    picks, is_weekend = calculate_picks(target_d)
    return jsonify({
        'picks': picks, 
        'is_weekend': is_weekend, 
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
    <title>Quant Lottery Mobile App</title>
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
        /* Smooth iOS Scrolling */
        * { -webkit-tap-highlight-color: transparent; }
    </style>
</head>
<body class="pb-28 select-none antialiased min-h-screen">

    <!-- Top App Header -->
    <header class="sticky top-0 z-40 glass px-4 py-3 flex items-center justify-between border-b border-darkBorder shadow-lg">
        <div class="flex items-center space-x-2.5">
            <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-500 to-teal-400 flex items-center justify-center shadow-emerald-500/30 shadow-lg">
                <i class="fa-solid fa-chart-line text-slate-900 text-lg font-black"></i>
            </div>
            <div>
                <h1 class="font-extrabold text-base tracking-wide bg-gradient-to-r from-emerald-400 to-teal-200 bg-clip-text text-transparent">Simons Quant</h1>
                <p class="text-[10px] text-emerald-400 font-medium flex items-center gap-1">
                    <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                    <span id="headerSub">เลขเด่นสด & ตรวจผล AI</span>
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

            <div id="picksLoading" class="py-16 text-center text-gray-400 space-y-2">
                <i class="fa-solid fa-circle-notch fa-spin text-3xl text-emerald-400"></i>
                <p class="text-xs font-medium">กำลังคำนวณสูตร Quant Model ล่าสุด...</p>
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
                    <p class="text-xs text-gray-400">ประวัติผลรางวัล & ตรวจสอบกำไรสุทธิรายวัน</p>
                </div>
                <span class="px-2.5 py-1 text-[11px] font-bold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30" id="resTotalDays">
                    - วัน
                </span>
            </div>

            <!-- Quick Summary Card -->
            <div class="glass rounded-2xl p-4 border border-emerald-500/30 bg-gradient-to-br from-darkCard to-slate-900 shadow-xl space-y-3">
                <div class="flex justify-between items-center border-b border-darkBorder/60 pb-2.5">
                    <span class="text-xs font-bold text-gray-300 flex items-center gap-1.5">
                        <i class="fa-solid fa-fire text-amber-400"></i> ผลตอบแทนสะสม (ทุกโมเดล)
                    </span>
                    <span class="text-[11px] font-bold text-emerald-400" id="cardRoiText"></span>
                </div>
                <div class="grid grid-cols-3 gap-2 text-center">
                    <div class="p-2 rounded-xl bg-slate-900/60 border border-darkBorder">
                        <p class="text-[9px] text-gray-400">กำไร 3 ตัว</p>
                        <p class="text-sm font-bold text-orange-400" id="cardProfit3d">+0 ฿</p>
                    </div>
                    <div class="p-2 rounded-xl bg-slate-900/60 border border-darkBorder">
                        <p class="text-[9px] text-gray-400">กำไร 2D Matrix</p>
                        <p class="text-sm font-bold text-teal-400" id="cardProfit2d">+0 ฿</p>
                    </div>
                    <div class="p-2 rounded-xl bg-slate-900/60 border border-darkBorder">
                        <p class="text-[9px] text-gray-400">กำไร 19 ประตู</p>
                        <p class="text-sm font-bold text-emerald-400" id="cardProfit19d">+0 ฿</p>
                    </div>
                </div>
                <div class="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex justify-between items-center mt-2">
                    <span class="text-xs text-emerald-400 font-medium">กำไรสุทธิรวม (Total Profit)</span>
                    <span class="text-lg font-black text-emerald-400" id="cardTotalProfitAll">+0 ฿</span>
                </div>
            </div>
            
            <!-- Model Selection Filter Control Bar -->
            <div class="glass p-3.5 rounded-2xl border border-darkBorder bg-darkCard/80 space-y-2">
                <div class="flex justify-between items-center text-xs">
                    <span class="font-extrabold text-gray-200 flex items-center gap-1.5">
                        <i class="fa-solid fa-sliders text-teal-400"></i> เลือกคำนวณผลรวมมุมขวา:
                    </span>
                    <span class="text-[10px] text-emerald-400 font-bold" id="filterStatusText">รวมครบ 3 โมเดล</span>
                </div>
                <div class="grid grid-cols-3 gap-2">
                    <button onclick="toggleModelFilter('3d')" id="btnFilter3d" class="py-2 px-1.5 rounded-xl text-xs font-bold border transition flex items-center justify-center gap-1 bg-orange-500/20 text-orange-300 border-orange-500/40 active:scale-95">
                        <i class="fa-solid fa-square-check" id="iconFilter3d"></i> 3 ตัวตรง
                    </button>
                    <button onclick="toggleModelFilter('2d')" id="btnFilter2d" class="py-2 px-1.5 rounded-xl text-xs font-bold border transition flex items-center justify-center gap-1 bg-teal-500/20 text-teal-300 border-teal-500/40 active:scale-95">
                        <i class="fa-solid fa-square-check" id="iconFilter2d"></i> 2D Matrix
                    </button>
                    <button onclick="toggleModelFilter('19d')" id="btnFilter19d" class="py-2 px-1.5 rounded-xl text-xs font-bold border transition flex items-center justify-center gap-1 bg-emerald-500/20 text-emerald-300 border-emerald-500/40 active:scale-95">
                        <i class="fa-solid fa-square-check" id="iconFilter19d"></i> 19 ประตู
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
                <p class="text-xs text-gray-400">เปรียบเทียบผลลัพธ์ระหว่างวันธรรมดา vs วันเสาร์-อาทิตย์</p>
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
                        <span class="text-gray-400">เข้าเบิ้ล 2 เด้ง (19 ประตู)</span>
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
            }
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        async function loadPicks() {
            try {
                const res = await fetch('/api/picks');
                const data = await res.json();
                document.getElementById('picksDateHeader').innerText = `งวดประจำวันที่ ${data.date}`;
                document.getElementById('marketBadge').innerText = data.is_weekend ? '🌴 หวยวันหยุด (ส-อา)' : '💼 ตลาดหุ้นหลัก (จ-ศ)';
                
                const container = document.getElementById('picksContainer');
                container.innerHTML = '';
                
                data.picks.forEach((it, idx) => {
                    const card = document.createElement('div');
                    card.className = 'glass rounded-2xl p-4 border border-darkBorder space-y-3.5 shadow-lg';
                    
                    let hPills = it.h_top.map(x => `<span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold text-xs border border-emerald-500/30">${x}</span>`).join(' ');
                    let tPills = it.t_top.map(x => `<span class="px-2 py-0.5 rounded bg-teal-500/20 text-teal-300 font-bold text-xs border border-teal-500/30">${x}</span>`).join(' ');
                    let doorsPills = it.top3_digits_doors.map(x => `<span class="px-2.5 py-0.5 rounded-lg bg-amber-500/20 text-amber-300 font-extrabold text-sm border border-amber-500/40">${x}</span>`).join(' ');
                    
                    card.innerHTML = `
                        <div class="flex items-center justify-between border-b border-darkBorder/50 pb-2">
                            <div>
                                <h3 class="font-extrabold text-base text-white">${it.name}</h3>
                                <p class="text-[11px] text-gray-400">ปิดรับ: <span class="text-emerald-400 font-semibold">${it.draw_time}</span></p>
                            </div>
                            <span class="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded-full font-bold">Quant Live</span>
                        </div>

                        <!-- 1. 2D 19 Doors 51 (MAIN MODEL) -->
                        <div class="p-3 rounded-xl bg-gradient-to-br from-amber-500/10 to-slate-900 border border-amber-500/40 space-y-2">
                            <div class="flex justify-between items-center">
                                <span class="text-xs font-bold text-amber-300 flex items-center gap-1.5">
                                    <i class="fa-solid fa-fire text-amber-400"></i> 🔥 2 ตัว รูด 19 ประตู (51 ตัว)
                                </span>
                                <span class="text-[10px] font-bold text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded">ลุ้น 2 เด้ง</span>
                            </div>
                            <div class="text-xs text-gray-300 flex items-center gap-2">
                                <span class="text-gray-400">3 เลขเด่น:</span> ${doorsPills}
                            </div>
                            <div class="grid grid-cols-2 gap-2 pt-1">
                                <button onclick="copyRaw('${it.nums_doors_comma}', '19 ประตู คั่นจุลภาค (,)', '${it.name}')" class="py-2 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-300 text-xs font-bold flex items-center justify-center gap-1.5 active:scale-95 transition">
                                    <i class="fa-regular fa-copy"></i> คัดลอก (19 ประตู)
                                </button>
                                <button onclick="copyRaw('${it.nums_doors_space}', '19 ประตู เว้นวรรค', '${it.name}')" class="py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-600 text-gray-300 text-xs font-semibold flex items-center justify-center gap-1.5 active:scale-95 transition">
                                    <i class="fa-solid fa-font"></i> คัดลอก (วรรค)
                                </button>
                            </div>
                        </div>

                        <!-- 2. 2D Matrix 30 -->
                        <div class="p-2.5 rounded-xl bg-slate-900/80 border border-teal-500/30 space-y-1.5">
                            <div class="flex justify-between items-center text-xs font-bold text-teal-300">
                                <span>⚡ 2 ตัวตรง Matrix 30 ตัว (5 สิบ × 6 หน่วย)</span>
                                <span class="text-[10px] text-teal-400">ทุน 30฿</span>
                            </div>
                            <button onclick="copyRaw('${it.nums_2d_comma}', '2 ตัว Matrix 30 ตัว', '${it.name}')" class="w-full py-1.5 rounded-lg bg-teal-500/20 hover:bg-teal-500/30 border border-teal-500/40 text-teal-300 text-xs font-semibold flex items-center justify-center gap-1.5 active:scale-95 transition">
                                <i class="fa-regular fa-copy"></i> คัดลอก 2 ตัวตรง (30 ตัว)
                            </button>
                        </div>

                        <!-- 3. 3D Top 120 -->
                        <div class="p-2.5 rounded-xl bg-slate-900/80 border border-emerald-500/30 space-y-1.5">
                            <div class="flex justify-between items-center text-xs font-bold text-emerald-300">
                                <span>🎯 3 ตัวตรง (4×3 Grid = 120 ตัว)</span>
                                <span class="text-[10px] text-emerald-400">ทุน 120฿ จ่าย 850฿</span>
                            </div>
                            <div class="text-[10px] text-gray-400 flex gap-2">
                                <span>ร้อย: ${hPills}</span>
                                <span>สิบ: ${tPills}</span>
                            </div>
                            <button onclick="copyRaw('${it.nums_3d_comma}', '3 ตัวตรง 120 ตัว', '${it.name}')" class="w-full py-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 text-xs font-semibold flex items-center justify-center gap-1.5 active:scale-95 transition">
                                <i class="fa-regular fa-copy"></i> คัดลอก 3 ตัวตรง (120 ตัว)
                            </button>
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

        function renderChart(historyData) {
            const ctx = document.getElementById('profitChart');
            if (!ctx) return;
            
            // Reverse history to chronological order (oldest to newest)
            const chronoData = [...historyData].reverse();
            
            const labels = chronoData.map(h => h.raw_date);
            
            let cum19d = 0;
            const data19d = chronoData.map(h => { cum19d += h.profit_19d; return cum19d; });
            
            let cum2d = 0;
            const data2d = chronoData.map(h => { cum2d += h.profit_2d; return cum2d; });
            
            let cum3d = 0;
            const data3d = chronoData.map(h => { cum3d += h.profit_3d; return cum3d; });
            
            if (profitChartInstance) {
                profitChartInstance.destroy();
            }
            
            profitChartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: '3 ตัวตรง',
                            data: data3d,
                            borderColor: '#F59E0B',
                            backgroundColor: 'rgba(245, 158, 11, 0.1)',
                            borderWidth: 2,
                            tension: 0.3,
                            pointRadius: 0,
                            pointHitRadius: 10
                        },
                        {
                            label: '2 ตัว Matrix',
                            data: data2d,
                            borderColor: '#14B8A6',
                            backgroundColor: 'rgba(20, 184, 166, 0.1)',
                            borderWidth: 2,
                            tension: 0.3,
                            pointRadius: 0,
                            pointHitRadius: 10
                        },
                        {
                            label: '19 ประตู',
                            data: data19d,
                            borderColor: '#10B981',
                            backgroundColor: 'rgba(16, 185, 129, 0.1)',
                            borderWidth: 2,
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
                                boxWidth: 10
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

        let selectedModels = { '3d': true, '2d': true, '19d': true };

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
                '2d': { btn: 'btnFilter2d', icon: 'iconFilter2d', active: 'bg-teal-500/20 text-teal-300 border-teal-500/40', inactive: 'bg-slate-900/60 text-gray-500 border-slate-700' },
                '19d': { btn: 'btnFilter19d', icon: 'iconFilter19d', active: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40', inactive: 'bg-slate-900/60 text-gray-500 border-slate-700' }
            };
            
            for (let k in config) {
                const c = config[k];
                const btn = document.getElementById(c.btn);
                const icon = document.getElementById(c.icon);
                if (btn && icon) {
                    if (selectedModels[k]) {
                        btn.className = `py-2 px-1.5 rounded-xl text-xs font-bold border transition flex items-center justify-center gap-1 active:scale-95 ${c.active}`;
                        icon.className = 'fa-solid fa-square-check';
                    } else {
                        btn.className = `py-2 px-1.5 rounded-xl text-xs font-bold border transition flex items-center justify-center gap-1 active:scale-95 ${c.inactive}`;
                        icon.className = 'fa-regular fa-square';
                    }
                }
            }
            
            const names = [];
            if (selectedModels['3d']) names.push('3 ตัว');
            if (selectedModels['2d']) names.push('2D');
            if (selectedModels['19d']) names.push('19D');
            const el = document.getElementById('filterStatusText');
            if (el) el.innerText = names.length === 3 ? 'รวมครบ 3 โมเดล' : `รวม: ${names.join(' + ')}`;
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
            let totalProfit2d = 0;
            let totalProfit19d = 0;
            
            data.history.forEach(h => {
                totalProfit3d += h.profit_3d;
                totalProfit2d += h.profit_2d;
                totalProfit19d += h.profit_19d;
            });
            
            let filteredTotalProfit = 0;
            if (selectedModels['3d']) filteredTotalProfit += totalProfit3d;
            if (selectedModels['2d']) filteredTotalProfit += totalProfit2d;
            if (selectedModels['19d']) filteredTotalProfit += totalProfit19d;

            document.getElementById('cardProfit3d').innerText = `${totalProfit3d > 0 ? '+' : ''}${totalProfit3d.toLocaleString()} ฿`;
            document.getElementById('cardProfit2d').innerText = `${totalProfit2d > 0 ? '+' : ''}${totalProfit2d.toLocaleString()} ฿`;
            document.getElementById('cardProfit19d').innerText = `${totalProfit19d > 0 ? '+' : ''}${totalProfit19d.toLocaleString()} ฿`;
            document.getElementById('cardTotalProfitAll').innerText = `${filteredTotalProfit > 0 ? '+' : ''}${filteredTotalProfit.toLocaleString()} ฿`;

            // Render Chart
            renderChart(data.history);

            // Tab 3 Stats Computation based on selection
            let wdWinDays = 0, wdLossDays = 0;
            let weWinDays = 0, weLossDays = 0;
            let wdProfit = 0, weProfit = 0;
            let wdBets = 0, weBets = 0;
            let wdDoubles = 0;
            
            data.history.forEach(h => {
                let hFilteredProfit = 0;
                let hFilteredBets = 0;
                if (selectedModels['3d']) { hFilteredProfit += h.profit_3d; hFilteredBets += h.bets_3d; }
                if (selectedModels['2d']) { hFilteredProfit += h.profit_2d; hFilteredBets += h.bets_2d; }
                if (selectedModels['19d']) { hFilteredProfit += h.profit_19d; hFilteredBets += h.bets_19d; }
                
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
            
            data.history.forEach((h, idx) => {
                const card = document.createElement('div');
                card.className = 'glass rounded-2xl p-3.5 border border-darkBorder space-y-2.5 shadow-md';
                
                let dayProfit = 0;
                if (selectedModels['3d']) dayProfit += h.profit_3d;
                if (selectedModels['2d']) dayProfit += h.profit_2d;
                if (selectedModels['19d']) dayProfit += h.profit_19d;
                
                const statusBadge = dayProfit > 0 
                    ? `<span class="px-2 py-0.5 rounded-full text-[11px] font-extrabold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"><i class="fa-solid fa-check"></i> กำไร +${dayProfit.toLocaleString()} ฿</span>`
                    : dayProfit < 0
                    ? `<span class="px-2 py-0.5 rounded-full text-[11px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30"><i class="fa-solid fa-xmark"></i> ติดลบ ${Math.abs(dayProfit).toLocaleString()} ฿</span>`
                    : `<span class="px-2 py-0.5 rounded-full text-[11px] font-bold bg-slate-800 text-gray-400 border border-slate-700">➖ เท่าทุน 0 ฿</span>`;
                    
                let drawsHtml = h.draws.map(d => {
                    let hitBadge19 = '';
                    if (d.is_double_19d) {
                        hitBadge19 = `<span class="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-extrabold text-[10px] border border-amber-500/40">🎯🎯 19D 2เด้ง (+129฿)</span>`;
                    } else if (d.hit_19d) {
                        hitBadge19 = `<span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold text-[10px] border border-emerald-500/30">🎯 19D 1เด้ง (+39฿)</span>`;
                    } else {
                        hitBadge19 = `<span class="px-2 py-0.5 rounded bg-slate-800 text-gray-400 text-[10px] border border-slate-700">❌ 19D หลุด (-51฿)</span>`;
                    }

                    let hitBadge2d = d.hit_2d 
                        ? `<span class="px-2 py-0.5 rounded bg-teal-500/20 text-teal-300 font-semibold text-[10px] border border-teal-500/30">⚡ 2D เข้า (+60฿)</span>` 
                        : `<span class="px-2 py-0.5 rounded bg-slate-800 text-gray-400 text-[10px] border border-slate-700">❌ 2D หลุด (-30฿)</span>`;
                        
                    let hitBadge3d = d.hit_3d 
                        ? `<span class="px-2 py-0.5 rounded bg-orange-500/20 text-orange-300 font-semibold text-[10px] border border-orange-500/30">🔥 3D แตก (+730฿)</span>` 
                        : `<span class="px-2 py-0.5 rounded bg-slate-800 text-gray-400 text-[10px] border border-slate-700">❌ 3D หลุด (-120฿)</span>`;

                    return `
                        <div class="flex items-center justify-between p-2 rounded-xl bg-slate-900/60 border border-darkBorder/50 text-xs">
                            <div class="min-w-0 flex-1">
                                <span class="font-bold text-white">${d.name}</span>
                                <div class="text-[10px] text-gray-400 flex flex-wrap gap-1.5 mt-0.5">
                                    <span>ออก: <b class="text-white">${d.actual_top3}</b> (${d.actual_2d})</span>
                                    <span>•</span>
                                    <span>เด่น: <b class="text-amber-300">[${d.top3_digits_doors.join(', ')}]</b></span>
                                </div>
                            </div>
                            <div class="text-right flex flex-col gap-1 items-end shrink-0 pl-2">
                                ${hitBadge3d}
                                ${hitBadge2d}
                                ${hitBadge19}
                            </div>
                        </div>
                    `;
                }).join('');
                
                card.innerHTML = `
                    <div class="flex items-center justify-between border-b border-darkBorder/40 pb-2">
                        <div>
                            <span class="font-black text-sm text-white">${h.day_name}ที่ ${h.raw_date}</span>
                            <span class="text-[10px] text-gray-400 ml-1.5">${h.is_weekend ? 'วันหยุด' : 'วันธรรมดา'}</span>
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
                if (currentTab === 'results') loadHistory();
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
    print(" [>] STARTING FULL QUANT LOTTERY MOBILE APP (WITH RESULTS & PICKS)")
    print("=" * 70)
    print(f" [*] Mobile Link (Same Wi-Fi) : http://{local_ip}:{port}")
    print(f" [*] Localhost Link           : http://localhost:{port}")
    print("=" * 70)
    app.run(host='0.0.0.0', port=port, debug=False)

