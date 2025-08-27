#!/usr/bin/env python3
"""
Farcaster Auto Vote Script
Script untuk melakukan otomatisasi vote fuel frame di Farcaster
"""

import requests
import json
import time
import random
import uuid
import datetime
import pytz
from urllib.parse import unquote, quote
import os

def parse_iso_time(iso_string):
    """Parse ISO time string ke datetime object"""
    try:
        # Parse ISO format
        dt = datetime.datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt
    except:
        return None

def format_time_wib(dt):
    """Format datetime ke WIB timezone"""
    if not dt:
        return "Unknown"
    
    # Convert ke WIB (UTC+7)
    wib_tz = pytz.timezone('Asia/Jakarta')
    dt_wib = dt.astimezone(wib_tz)
    return dt_wib.strftime('%Y-%m-%d %H:%M:%S WIB')

def format_duration(seconds):
    """Format duration dalam seconds ke readable string"""
    if seconds <= 0:
        return "0s"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"

def format_time_diff(dt):
    """Format time difference menjadi readable string"""
    if not dt:
        return "Unknown"
    
    now = datetime.datetime.now(pytz.UTC)
    diff = dt - now
    
    if diff.total_seconds() < 0:
        # Waktu sudah lewat
        diff = abs(diff)
        total_seconds = int(diff.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m ago"
        elif minutes > 0:
            return f"{minutes}m {seconds}s ago"
        else:
            return f"{seconds}s ago"
    else:
        # Waktu di masa depan
        total_seconds = int(diff.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        if hours > 0:
            return f"in {hours}h {minutes}m"
        elif minutes > 0:
            return f"in {minutes}m {seconds}s"
        else:
            return f"in {seconds}s"

def show_match_timing_info(match_data):
    """Display match timing information"""
    print(f"\n⏰ MATCH TIMING INFO")
    print("=" * 50)
    
    # Parse times
    voting_start = parse_iso_time(match_data.get('votingStartTime'))
    voting_end = parse_iso_time(match_data.get('votingEndTime') or match_data.get('endTime'))
    match_start = parse_iso_time(match_data.get('startTime'))
    match_end = parse_iso_time(match_data.get('endTime'))
    
    print(f"🎯 Match ID: {match_data.get('_id')}")
    print(f"📊 Status: {match_data.get('status')}")
    print(f"🏆 Total Votes: {match_data.get('totalVotes', 0)}")
    
    now = datetime.datetime.now(pytz.UTC)
    print(f"🕐 Current Time: {format_time_wib(now)}")
    
    if voting_start and voting_end:
        print(f"\n📅 Voting Window:")
        print(f"   🟢 Start: {format_time_wib(voting_start)} ({format_time_diff(voting_start)})")
        print(f"   🔴 End: {format_time_wib(voting_end)} ({format_time_diff(voting_end)})")
        
        # Check voting status
        if now < voting_start:
            voting_status = f"⏳ Voting opens {format_time_diff(voting_start)}"
        elif now > voting_end:
            voting_status = f"⏰ Voting ended {format_time_diff(voting_end)}"
        else:
            voting_status = f"✅ Voting is OPEN (ends {format_time_diff(voting_end)})"
        
        print(f"\n🗳️  Status: {voting_status}")
    
    if match_start and match_end:
        print(f"\n🎮 Match Schedule:")
        print(f"   🏁 Start: {format_time_wib(match_start)} ({format_time_diff(match_start)})")
        print(f"   🏁 End: {format_time_wib(match_end)} ({format_time_diff(match_end)})")
    
    print("=" * 50)

class FarcasterAutoVote:
    def __init__(self, authorization_token, fuel_amount=None, max_fuel=5, team_preference=None, privy_token=None):
        """
        Initialize FarcasterAutoVote
        
        Args:
            authorization_token (str): Bearer token untuk authorization
            fuel_amount (int): Jumlah fuel yang ingin digunakan (1-max_fuel). Jika None, akan random
            max_fuel (int): Maximum fuel yang bisa digunakan (default: 5)
            team_preference (str): Preferensi tim - 'blue'/'biru', 'red'/'merah', atau None untuk auto-select terbaik
            privy_token (str): Token untuk Privy API
        """
        self.authorization_token = authorization_token
        self.privy_token = privy_token
        self.device_id = "BWlTSwbJOzW_A58ybrzqz6"  # Device ID dari endpoint.txt
        self.session_id = str(int(time.time() * 1000) - random.randint(1000, 5000))  # Generate session ID
        self.user_id = "1284274"  # User ID dari endpoint.txt
        self.fuel_amount = fuel_amount
        self.max_fuel = max_fuel
        self.team_preference = team_preference.lower() if team_preference else None
        self.base_headers = self._get_base_headers()
        
    def _get_base_headers(self):
        """Generate headers dasar untuk request"""
        return {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "authorization": f"Bearer {self.authorization_token}",
            "content-type": "application/json; charset=utf-8",
            "fc-amplitude-device-id": self.device_id,
            "fc-amplitude-session-id": self.session_id,
            "priority": "u=1, i",
            "sec-ch-ua": '"Not;A=Brand";v="99", "Microsoft Edge";v="139", "Chromium";v="139"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0"
        }
    
    def _generate_uuid(self):
        """Generate UUID untuk request"""
        return str(uuid.uuid4())
    
    def _generate_idempotency_key(self):
        """Generate idempotency key"""
        return str(uuid.uuid4())
    
    def get_frame_info(self, domain="versus.wreckleague.xyz"):
        """Mendapatkan informasi frame"""
        try:
            url = f"https://client.farcaster.xyz/v1/frame?domain={domain}"
            headers = self.base_headers.copy()
            headers["if-none-match"] = 'W/"hmuRfiKTIpNKs+g2C7YFhVWoFX4="'
            
            response = requests.get(url, headers=headers)
            print(f"Frame info response status: {response.status_code}")
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error getting frame info: {e}")
            return None
    
    def send_mini_app_event(self, domain="versus.wreckleague.xyz", event="open"):
        """Send mini app event"""
        try:
            url = "https://client.farcaster.xyz/v2/mini-app-event"
            headers = self.base_headers.copy()
            headers["idempotency-key"] = self._generate_idempotency_key()
            headers["traceparent"] = f"00-000000000000000000{random.randint(100000000000, 999999999999)}-{random.randint(1000000000000000, 9999999999999999):x}-01"
            headers["x-datadog-origin"] = "rum"
            headers["x-datadog-parent-id"] = str(random.randint(1000000000000000000, 9999999999999999999))
            headers["x-datadog-sampling-priority"] = "1"
            headers["x-datadog-trace-id"] = str(random.randint(1000000000000000, 9999999999999999999))
            
            payload = {
                "domain": domain,
                "event": event,
                "platformType": "web"
            }
            
            response = requests.put(url, headers=headers, json=payload)
            print(f"Mini app event response status: {response.status_code}")
            return response.status_code == 200
        except Exception as e:
            print(f"Error sending mini app event: {e}")
            return False
    
    def get_match_details(self, fid=None):
        """Mendapatkan detail match"""
        try:
            fid = fid or self.user_id
            url = f"https://versus-prod-api.wreckleague.xyz/v1/match/details?fId={fid}"
            
            headers = {
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "if-none-match": 'W/"100b-Y/gj6927mGNPyq8v7gTfbP0qRuM"',
                "priority": "u=1, i",
                "sec-ch-ua": '"Not;A=Brand";v="99", "Microsoft Edge";v="139", "Chromium";v="139"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0"
            }
            
            response = requests.get(url, headers=headers)
            print(f"Match details response status: {response.status_code}")
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error getting match details: {e}")
            return None
    
    def get_latest_match_id(self, fid=None):
        """Mendapatkan match ID terbaru yang tersedia"""
        try:
            fid = fid or self.user_id
            # Coba endpoint untuk list match atau active match
            url = f"https://versus-prod-api.wreckleague.xyz/v1/match/details?fId={fid}"
            
            headers = {
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "priority": "u=1, i",
                "sec-ch-ua": '"Not;A=Brand";v="99", "Microsoft Edge";v="139", "Chromium";v="139"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0"
            }
            
            response = requests.get(url, headers=headers)
            print(f"🔍 Checking for latest match... Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"🔍 Debug response structure: {json.dumps(data, indent=2)[:500]}...")
                
                if data.get('data') and data['data'].get('matchDetails'):
                    match_details = data['data']['matchDetails']
                    if isinstance(match_details, list) and len(match_details) > 0:
                        # Ambil match ID dari match pertama (biasanya yang terbaru)
                        latest_match = match_details[0]
                        match_id = latest_match.get('matchId')
                        if match_id:
                            print(f"✅ Found latest match ID: {match_id}")
                            return match_id
                        else:
                            print("⚠️ No match ID found in response")
                    else:
                        print("⚠️ No match details available")
                elif data.get('data') and data['data'].get('matchData'):
                    # Coba struktur alternatif
                    match_data = data['data']['matchData']
                    if isinstance(match_data, list) and len(match_data) > 0:
                        latest_match = match_data[0]
                        match_id = latest_match.get('_id')
                        if match_id:
                            print(f"✅ Found latest match ID from matchData: {match_id}")
                            return match_id
                        else:
                            print("⚠️ No _id found in matchData")
                    else:
                        print("⚠️ No match data available")
                else:
                    print("⚠️ No match data in response")
            else:
                print(f"❌ Failed to get latest match: {response.status_code}")
            
            return None
        except Exception as e:
            print(f"❌ Error getting latest match ID: {e}")
            return None
    
    def select_mech_by_preference(self, mech_details):
        """
        Pilih mech berdasarkan preferensi tim atau strategy terbaik
        
        Args:
            mech_details (list): List detail mech dari match
            
        Returns:
            dict: Mech yang dipilih
        """
        if not mech_details:
            return None
            
        if len(mech_details) == 1:
            return mech_details[0]
        
        # Jika ada preferensi tim
        if self.team_preference:
            # Coba identifikasi tim berdasarkan posisi atau data
            for i, mech in enumerate(mech_details):
                team_indicator = ""
                
                # CORRECTED MAPPING berdasarkan info user:
                # Biru = Kanan (index 1), Merah = Kiri (index 0)
                if i == 0:
                    team_indicator = "red"   # Index 0 = Kiri = Merah
                elif i == 1:
                    team_indicator = "blue"  # Index 1 = Kanan = Biru
                
                # Cek berdasarkan field mechType jika ada
                if 'mechType' in mech:
                    if mech['mechType'] == 'left':
                        team_indicator = "red"   # Left = Merah
                    elif mech['mechType'] == 'right':
                        team_indicator = "blue"  # Right = Biru
                
                # Cek berdasarkan publicPossession (yang lebih kecil biasanya merah/kiri)
                if not team_indicator and 'publicPossession' in mech:
                    possession = mech.get('publicPossession', 50)
                    # Tidak reliable untuk mapping, skip ini
                
                # Match dengan preferensi user (CORRECTED)
                if (self.team_preference in ['blue', 'biru', 'kanan', 'right'] and team_indicator == "blue") or \
                   (self.team_preference in ['red', 'merah', 'kiri', 'left'] and team_indicator == "red"):
                    print(f"🎯 Selected mech by team preference: {self.team_preference} -> {mech['mechId']}")
                    print(f"   Team: {team_indicator.upper()} (Index: {i})")
                    return mech
        
        # Jika tidak ada preferensi atau tidak ditemukan, pilih yang terbaik
        # Prioritas: 1. Winning probability, 2. Vote count, 3. Fuel points
        best_mech = max(mech_details, key=lambda m: (
            m.get('winningProbability', 0),
            m.get('mechVotes', {}).get('voteCount', 0),
            m.get('mechVotes', {}).get('fuelPoints', 0)
        ))
        
    def get_user_data(self, fid=None):
        """Mendapatkan data user"""
        try:
            fid = fid or self.user_id
            url = f"https://versus-prod-api.wreckleague.xyz/v1/user/data?fId={fid}"
            
            headers = {
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "if-none-match": 'W/"158-rOBHgTHczeddj//B7BCGN2xjD38"',
                "priority": "u=1, i",
                "sec-ch-ua": '"Not;A=Brand";v="99", "Microsoft Edge";v="139", "Chromium";v="139"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0"
            }
            
            response = requests.get(url, headers=headers)
            print(f"User data response status: {response.status_code}")
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error getting user data: {e}")
            return None
        
    def get_user_fuel_info(self, fid=None):
        """Mendapatkan info fuel user"""
        try:
            fid = fid or self.user_id
            url = f"https://versus-prod-api.wreckleague.xyz/v1/user/data?fId={fid}"
            
            headers = {
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "priority": "u=1, i",
                "sec-ch-ua": '"Not;A=Brand";v="99", "Microsoft Edge";v="139", "Chromium";v="139"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0"
            }
            
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                
                # Berdasarkan response yang dilihat: data.data.fuelBalance
                if 'data' in data and 'data' in data['data'] and 'fuelBalance' in data['data']['data']:
                    fuel_info = data['data']['data']['fuelBalance']
                    return fuel_info if fuel_info > 0 else 0
                
            return 0
        except Exception as e:
            return 0
        """Mendapatkan data user"""
        try:
            fid = fid or self.user_id
            url = f"https://versus-prod-api.wreckleague.xyz/v1/user/data?fId={fid}"
            
            headers = {
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "if-none-match": 'W/"158-rOBHgTHczeddj//B7BCGN2xjD38"',
                "priority": "u=1, i",
                "sec-ch-ua": '"Not;A=Brand";v="99", "Microsoft Edge";v="139", "Chromium";v="139"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0"
            }
            
            response = requests.get(url, headers=headers)
            print(f"User data response status: {response.status_code}")
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error getting user data: {e}")
            return None
        """Mendapatkan data user"""
        try:
            fid = fid or self.user_id
            url = f"https://versus-prod-api.wreckleague.xyz/v1/user/data?fId={fid}"
            
            headers = {
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "if-none-match": 'W/"158-rOBHgTHczeddj//B7BCGN2xjD38"',
                "priority": "u=1, i",
                "sec-ch-ua": '"Not;A=Brand";v="99", "Microsoft Edge";v="139", "Chromium";v="139"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0"
            }
            
            response = requests.get(url, headers=headers)
            print(f"User data response status: {response.status_code}")
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error getting user data: {e}")
            return None
    
    def submit_prediction(self, fid=None, mech_id=None, match_id=None, fuel_points=None):
        """Submit prediction/vote dengan fuel points"""
        try:
            fid = fid or self.user_id
            
            # Auto-detect latest match ID jika tidak disediakan
            if not match_id:
                print("🔍 Auto-detecting latest match ID...")
                match_id = self.get_latest_match_id(fid)
                if not match_id:
                    print("❌ Could not auto-detect match ID")
                    return False
                print(f"✅ Using auto-detected match ID: {match_id}")
            
            # Ambil match details untuk data terbaru  
            match_details = self.get_match_details(fid)
            if not match_details or 'data' not in match_details or not match_details['data']['matchData']:
                print("❌ No active match found")
                return False

            current_match = match_details['data']['matchData'][0]
            
            # Cek apakah sudah vote - tapi tetap lanjut karena bisa vote tim yang sama
            if current_match.get('isVoted', False):
                print("ℹ️  Previous vote detected, checking if additional vote possible...")
                # Tidak langsung return False, tapi lanjut coba vote
            
            # Update match ID dari current match jika berbeda
            detected_match_id = current_match['_id']
            if match_id != detected_match_id:
                print(f"🔄 Updating match ID: {match_id} → {detected_match_id}")
                match_id = detected_match_id
            
            # Auto-detect available mech IDs from current match
            available_mechs = current_match.get('mechIds', [])
            if available_mechs:
                print(f"🔍 Auto-detected available mechs: {available_mechs}")
            
            # Pilih mech berdasarkan preferensi atau strategy
            if not mech_id and 'mechDetails' in current_match:
                mech_details = current_match['mechDetails']
                selected_mech = self.select_mech_by_preference(mech_details)
                
                if selected_mech:
                    mech_id = selected_mech['mechId']
                    
                    # Tampilkan info mech yang dipilih
                    team_info = ""
                    if len(mech_details) >= 2:
                        mech_index = next((i for i, m in enumerate(mech_details) if m['mechId'] == mech_id), -1)
                        if mech_index == 0:
                            team_info = " (� Tim Merah/Kiri)"  # Index 0 = Merah = Kiri
                        elif mech_index == 1:
                            team_info = " (� Tim Biru/Kanan)"  # Index 1 = Biru = Kanan
                    
                    print(f"🎯 Selected mech {mech_id}{team_info}")
                    print(f"   👤 Owner: {selected_mech['userData']['displayName']}")
                    print(f"   🏆 Win Probability: {selected_mech.get('winningProbability', 0)}%")
                    print(f"   🗳️  Current Votes: {selected_mech.get('mechVotes', {}).get('voteCount', 0)}")
                    print(f"   ⛽ Current Fuel: {selected_mech.get('mechVotes', {}).get('fuelPoints', 0)}")
                else:
                    # Fallback ke mech ID pertama yang tersedia dari current match
                    available_mechs = current_match.get('mechIds', [])
                    if available_mechs:
                        mech_id = available_mechs[0]
                        print(f"🎯 Using first available mech ID: {mech_id}")
                    else:
                        print("❌ No mech IDs available")
                        return False
            elif not mech_id:
                # Jika tidak ada mechDetails, gunakan mechIds yang tersedia
                available_mechs = current_match.get('mechIds', [])
                if available_mechs:
                    mech_id = available_mechs[0]  # Ambil yang pertama
                    print(f"🎯 Using first available mech ID: {mech_id}")
                else:
                    print("❌ No mech data available")
                    return False
            
            # Tentukan jumlah fuel berdasarkan setting
            if not fuel_points:
                if self.fuel_amount:
                    # Cek apakah fuel amount tidak melebihi max fuel
                    if self.fuel_amount > self.max_fuel:
                        print(f"⚠️  Fuel amount ({self.fuel_amount}) melebihi max fuel ({self.max_fuel})")
                        print("❌ FUEL TIDAK MENCUKUPI!")
                        print(f"   🔋 Fuel yang dibutuhkan: {self.fuel_amount}")
                        print(f"   💰 Fuel yang dimiliki: {self.max_fuel}")
                        return False
                    
                    fuel_points = self.fuel_amount
                    print(f"⛽ Using configured fuel amount: {fuel_points}")
                else:
                    print("❌ Fuel amount tidak ditentukan!")
                    return False
            
            
            url = "https://versus-prod-api.wreckleague.xyz/v2/matches/predict"
            
            headers = {
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "content-type": "application/json",
                "priority": "u=1, i",
                "sec-ch-ua": '"Not;A=Brand";v="99", "Microsoft Edge";v="139", "Chromium";v="139"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0"
            }
            
            payload = {
                "fId": int(fid),
                "mechId": str(mech_id),
                "matchId": str(match_id),
                "fuelPoints": int(fuel_points)
            }
            
            print(f"🚀 Submitting prediction with payload: {payload}")
            
            response = requests.put(url, headers=headers, json=payload)
            print(f"Prediction submission response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Prediction submitted successfully!")
                print(f"📊 Result: {result}")
                return True
            else:
                print(f"❌ Prediction submission failed with status {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"📄 Error details: {error_data}")
                    
                    # Cek jenis error
                    if 'message' in error_data:
                        error_msg = error_data['message']
                        if "cannot powerup at this time" in error_msg.lower():
                            print("ℹ️  Cannot powerup at this time")
                            print("🔍 Possible reasons:")
                            print("   - Voting window closed")
                            print("   - Already voted for different team")
                            print("   - Match ended")
                            print("💡 Try selecting the SAME team you voted before")
                        elif "already voted" in error_msg.lower():
                            print("ℹ️  Already voted for this match")
                            print("💡 You can vote again but only for the SAME team!")
                            print("   - Biru = Kanan (Right)")
                            print("   - Merah = Kiri (Left)")
                        elif "insufficient fuel" in error_msg.lower():
                            print("⛽ Insufficient fuel points")
                        elif "invalid match" in error_msg.lower():
                            print("🎯 Match might be inactive or ended")
                        else:
                            print(f"📝 Error message: {error_msg}")
                except:
                    print(f"📄 Raw response: {response.text}")
                return False
                
        except Exception as e:
            print(f"Error submitting prediction: {e}")
            return False
    
    def send_amplitude_tracking(self, event_type="frame action", action="add mini app"):
        """Send amplitude tracking event"""
        try:
            url = "https://client.farcaster.xyz/v2/amp/api"
            
            headers = {
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "cross-origin-resource-policy": "cross-origin",
                "priority": "u=1, i",
                "sec-ch-ua": '"Not;A=Brand";v="99", "Microsoft Edge";v="139", "Chromium";v="139"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0"
            }
            
            timestamp = int(time.time() * 1000)
            event_id = random.randint(140, 200)
            
            event_data = {
                "device_id": self.device_id,
                "user_id": self.user_id,
                "timestamp": timestamp,
                "event_id": event_id,
                "session_id": self.session_id,
                "event_type": event_type,
                "version_name": None,
                "platform": "Web",
                "os_name": "Edge",
                "os_version": "139",
                "device_model": "Windows",
                "device_manufacturer": None,
                "language": "en-US",
                "api_properties": {},
                "event_properties": {
                    "action": action,
                    "frameDomain": "versus.wreckleague.xyz",
                    "frameName": "Wreck League Versus",
                    "alreadyFavorited": True,
                    "path": "/miniapps",
                    "warpcastPlatform": "web"
                },
                "user_properties": {},
                "uuid": self._generate_uuid(),
                "library": {
                    "name": "amplitude-js",
                    "version": "8.21.9"
                },
                "sequence_number": event_id,
                "groups": {},
                "group_properties": {},
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0",
                "partner_id": None
            }
            
            checksum = "c637ef550ee809550511f2993af810c3"  # Dapat digenerate atau hardcode
            client = "7dd7b12861158f5e89ab5508bd9ce4c0"
            
            payload = f"checksum={checksum}&client={client}&e={quote(json.dumps([event_data]))}&upload_time={timestamp}&v=2"
            
            response = requests.post(url, headers=headers, data=payload)
            print(f"Amplitude tracking response status: {response.status_code}")
            
            return response.status_code == 200
        except Exception as e:
            print(f"Error sending amplitude tracking: {e}")
            return False
    
    def trigger_share_task(self):
        """Trigger share task untuk mendapatkan task 5 like = 1 fuel"""
        try:
            # Endpoint untuk trigger analysis task (dari share_endpoint.txt)
            url = "https://versus-prod-api.wreckleague.xyz/v1/analysis"
            
            headers = {
                "Authorization": f"Bearer {self.authorization_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            print(f"🎯 Triggering share task...")
            response = requests.post(url, headers=headers)
            
            if response.status_code == 200:
                print(f"   ✅ Share task triggered successfully")
                return True
            else:
                print(f"   ❌ Failed to trigger share task: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   ❌ Error triggering share task: {e}")
            return False

    def auto_share_cast(self, custom_text=None):
        """Auto share cast workflow: trigger task dulu, lalu post cast untuk dapat like"""
        try:
            # Step 1: Trigger share task dulu
            if not self.trigger_share_task():
                print("❌ Failed to trigger share task, skipping cast posting")
                return False
                
            # Delay sebentar
            time.sleep(2)
            
            # Step 2: Post cast untuk promosi dan dapat like
            url = "https://client.farcaster.xyz/v2/casts"
            
            # Headers berdasarkan data di share_endpoint.txt
            headers = self.base_headers.copy()
            headers.update({
                "idempotency-key": self._generate_idempotency_key(),
                "traceparent": f"00-000000000000000000{random.randint(100000000000, 999999999999)}-{random.randint(1000000000000000, 9999999999999999):x}-01",
                "x-datadog-origin": "rum",
                "x-datadog-parent-id": str(random.randint(1000000000000000000, 9999999999999999999)),
                "x-datadog-sampling-priority": "1",
                "x-datadog-trace-id": str(random.randint(1000000000000000, 9999999999999999999))
            })
            
            # Template text atau custom
            if custom_text:
                cast_text = custom_text
            else:
                # Random variasi text dengan typo natural untuk avoid spam detection
                text_variations = [
                    "Help me get Fuel by likeing this cast!\n5 Likes = 1 Fuel🔋\nSupport my mech battles in Wreck League Versus 🤖 by @towerecosystem",
                    "Pls help me get Fuel by liking this cast!\n5 Like = 1 Fuel🔋\nSuport my mech battles in Wreck League Versus 🤖 by @towerecosystem", 
                    "Help me get Fuel by likng this cast!\n5 Likes = 1 Fuel🔋\nSupport my mech batles in Wreck League Versus 🤖 by @towerecosystem",
                    "Help me get Fuel by liking this cast pls!\n5 Likes = 1 Fuel🔋\nSupport my mech battles in Wreck League Versus 🤖 by @towerecosystem",
                    "Help me get Fuel by liking this cast!\n5 Likes = 1 Fuel🔋\nSupport my mech battles in Wreck League Versus 🤖 by @towerecosystem thx!",
                    "Hlp me get Fuel by liking this cast!\n5 Likes = 1 Fuel🔋\nSupport my mech battles in Wreck League Versus 🤖 by @towerecosystem",
                    "Help me get Fuel by liking this cast!\n5 likes = 1 fuel🔋\nSupport my mech battles in Wreck League Versus 🤖 by @towerecosystem",
                    "Help me get Fuel by likeing this cast plz!\n5 Likes = 1 Fuel🔋\nSupport my mech battles in Wreck League Versus 🤖 by @towerecosystem"
                ]
                cast_text = random.choice(text_variations)
            
            # Payload
            payload = {
                "text": cast_text,
                "embeds": [f"https://versus.wreckleague.xyz/{self.user_id}"]
            }
            
            print(f"📝 Posting promotional cast...")
            print(f"   Text: {cast_text[:50]}...")
            print(f"   Embed: https://versus.wreckleague.xyz/{self.user_id}")
            
            response = requests.post(url, headers=headers, json=payload)
            print(f"Cast submission response status: {response.status_code}")
            
            if response.status_code in [200, 201]:  # 200 OK atau 201 Created
                result = response.json()
                print("✅ Cast posted successfully!")
                
                # Tambahkan tracking untuk cast message (dari share_endpoint.txt)
                self.send_cast_tracking()
                
                if 'result' in result and 'cast' in result['result']:
                    cast_info = result['result']['cast']
                    print(f"📊 Cast details:")
                    print(f"   🆔 Cast hash: {cast_info.get('hash', 'Unknown')}")
                    print(f"   👤 Author: {cast_info.get('author', {}).get('username', 'Unknown')}")
                    print(f"   📅 Timestamp: {cast_info.get('timestamp', 'Unknown')}")
                    print(f"   📝 Text: {cast_info.get('text', 'Unknown')[:50]}...")
                    
                return True
            else:
                print(f"❌ Cast submission failed with status {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"📄 Error details: {error_data}")
                    
                    if 'message' in error_data:
                        error_msg = error_data['message']
                        if "duplicate" in error_msg.lower():
                            print("ℹ️  Duplicate cast detected - you recently posted similar content")
                        elif "rate limit" in error_msg.lower():
                            print("ℹ️  Rate limited - please wait before posting again")
                        elif "invalid" in error_msg.lower():
                            print("ℹ️  Invalid cast format")
                        else:
                            print(f"📝 Error message: {error_msg}")
                except:
                    print(f"📄 Raw response: {response.text}")
                return False
                
        except Exception as e:
            print(f"Error posting cast: {e}")
            return False
    
    def send_cast_tracking(self):
        """Send tracking untuk cast message berdasarkan share_endpoint.txt"""
        try:
            url = "https://client.farcaster.xyz/v2/amp/api"
            
            headers = {
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "cross-origin-resource-policy": "cross-origin",
                "priority": "u=1, i",
                "sec-ch-ua": '"Not;A=Brand";v="99", "Microsoft Edge";v="139", "Chromium";v="139"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0"
            }
            
            timestamp = int(time.time() * 1000)
            event_id = random.randint(150, 200)
            
            # Event data berdasarkan format di share_endpoint.txt
            event_data = {
                "device_id": self.device_id,
                "user_id": self.user_id,
                "timestamp": timestamp,
                "event_id": event_id,
                "session_id": self.session_id,
                "event_type": "cast message",  # Sesuai share_endpoint.txt
                "version_name": None,
                "platform": "Web",
                "os_name": "Edge",
                "os_version": "139",
                "device_model": "Windows",
                "device_manufacturer": None,
                "language": "en-US",
                "api_properties": {},
                "event_properties": {
                    "is reply": False,
                    "is channel": False,
                    "channel name": "",
                    "is long cast": False,
                    "is from intent": True,
                    "is caststrorm": 1,
                    "is scheduled": False,
                    "warpcastPlatform": "web"
                },
                "user_properties": {},
                "uuid": self._generate_uuid(),
                "library": {
                    "name": "amplitude-js",
                    "version": "8.21.9"
                },
                "sequence_number": event_id,
                "groups": {},
                "group_properties": {},
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0",
                "partner_id": None
            }
            
            # Checksum dari share_endpoint.txt
            checksum = "164f2070e0f5360795d082772f7b168e"
            client = "7dd7b12861158f5e89ab5508bd9ce4c0"
            
            payload = f"checksum={checksum}&client={client}&e={quote(json.dumps([event_data]))}&upload_time={timestamp}&v=2"
            
            response = requests.post(url, headers=headers, data=payload)
            print(f"Cast tracking response status: {response.status_code}")
            
            return response.status_code == 200
        except Exception as e:
            print(f"Error sending cast tracking: {e}")
            return False
    
    def claim_fuel_reward(self):
        """Claim fuel reward setelah mendapat like yang cukup (dari share_endpoint.txt)"""
        try:
            # Endpoint untuk claim fuel reward
            url = f"https://versus-prod-api.wreckleague.xyz/v1/user/fuelReward?fId={self.user_id}"
            
            headers = {
                "Authorization": f"Bearer {self.authorization_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            print(f"⛽ Claiming fuel reward...")
            response = requests.post(url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                print(f"   ✅ Fuel reward claimed successfully!")
                if 'fuel' in result:
                    print(f"   ⛽ New fuel amount: {result['fuel']}")
                return True
            else:
                print(f"   ❌ Failed to claim fuel reward: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   📄 Error: {error_data}")
                except:
                    print(f"   📄 Raw response: {response.text}")
                return False
                
        except Exception as e:
            print(f"   ❌ Error claiming fuel reward: {e}")
            return False
    
    def check_share_details(self):
        """Check detailed share/cast information"""
        try:
            # Coba endpoint fuel reward untuk detail share
            url = f"https://versus-prod-api.wreckleague.xyz/v1/user/fuelReward?fId={self.user_id}"
            
            headers = {
                "Authorization": f"Bearer {self.authorization_token}",
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                return result
            else:
                print(f"Failed to check share details: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error checking share details: {e}")
            return None

    def check_fuel_status(self):
        """Check current fuel status sebelum claim"""
        try:
            # Endpoint untuk get fuel status
            url = f"https://versus-prod-api.wreckleague.xyz/v1/user/data?fId={self.user_id}"
            
            headers = {
                "Authorization": f"Bearer {self.authorization_token}",
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                return result
            else:
                print(f"Failed to check fuel status: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error checking fuel status: {e}")
            return None

    def try_different_triggers(self):
        """Try different trigger endpoints and methods"""
        triggers_to_try = [
            # Method 1: Analysis dengan matchId
            {
                "url": "https://versus-prod-api.wreckleague.xyz/v1/analysis?fId=1284274&matchId=68ac7d8db887790bf290ec13",
                "method": "POST",
                "name": "Analysis POST with matchId"
            },
            # Method 2: Analysis GET
            {
                "url": "https://versus-prod-api.wreckleague.xyz/v1/analysis",
                "method": "GET", 
                "name": "Analysis GET"
            },
            # Method 3: Analysis GET dengan fId
            {
                "url": "https://versus-prod-api.wreckleague.xyz/v1/analysis?fId=1284274",
                "method": "GET",
                "name": "Analysis GET with fId"
            },
            # Method 4: Match details POST
            {
                "url": "https://versus-prod-api.wreckleague.xyz/v1/match/details?fId=1284274",
                "method": "POST",
                "name": "Match details POST"
            }
        ]
        
        headers = {
            "Authorization": f"Bearer {self.authorization_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        print("🔍 TESTING DIFFERENT TRIGGER METHODS")
        print("=" * 40)
        
        for i, trigger in enumerate(triggers_to_try, 1):
            print(f"{i}. Testing: {trigger['name']}")
            print(f"   URL: {trigger['url']}")
            print(f"   Method: {trigger['method']}")
            
            try:
                if trigger['method'] == 'POST':
                    response = requests.post(trigger['url'], headers=headers)
                else:
                    response = requests.get(trigger['url'], headers=headers)
                
                print(f"   Status: {response.status_code}")
                
                if response.status_code == 200:
                    print("   ✅ SUCCESS!")
                    try:
                        result = response.json()
                        print(f"   Response: {result}")
                    except:
                        print(f"   Response: {response.text[:100]}")
                    return trigger['url'], trigger['method']
                else:
                    print(f"   ❌ Failed")
                    
            except Exception as e:
                print(f"   ❌ Error: {e}")
            
            print()
        
        print("❌ All trigger methods failed")
        return None, None

    def simple_share_process(self, custom_text=None):
        """Proses share sederhana - trigger task + post cast"""
        try:
            print("🚀 STARTING SHARE PROCESS")
            print("=" * 30)
            
            # 1. Trigger share task dengan method yang benar
            print("1. Triggering share task...")
            url = f"https://versus-prod-api.wreckleague.xyz/v1/analysis?fId={self.user_id}"
            headers = {
                "Authorization": f"Bearer {self.authorization_token}",
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            # GET analytics (working method)
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                print("   ✅ Analytics retrieved successfully")
                
                # Coba POST analytics event untuk share button click
                print("   📊 Sending share button analytics...")
                analytics_url = "https://versus-prod-api.wreckleague.xyz/v1/analysis"
                analytics_payload = {
                    "userName": "mrmoney",
                    "displayName": "Anthony ☠️",
                    "fId": int(self.user_id),
                    "eventType": 1,
                    "buttonId": "versus_share_btn",
                    "eventName": "Button Click"
                }
                
                analytics_headers = headers.copy()
                analytics_headers["Content-Type"] = "application/json"
                
                analytics_response = requests.post(analytics_url, headers=analytics_headers, json=analytics_payload)
                if analytics_response.status_code in [200, 201]:
                    print("   ✅ Share analytics sent successfully")
                else:
                    print(f"   ⚠️  Share analytics response: {analytics_response.status_code}")
                    
            else:
                print(f"   ❌ Analytics failed: {response.status_code}")
                return False
            
            time.sleep(2)
            
            # 2. Post promotional cast
            print("2. Posting promotional cast...")
            cast_url = "https://client.farcaster.xyz/v2/casts"
            
            cast_headers = self.base_headers.copy()
            cast_headers.update({
                "idempotency-key": self._generate_idempotency_key(),
                "traceparent": f"00-000000000000000000{random.randint(100000000000, 999999999999)}-{random.randint(1000000000000000, 9999999999999999):x}-01",
            })
            
            if custom_text:
                cast_text = custom_text
            else:
                # Random variasi text dengan typo natural untuk avoid spam detection
                text_variations = [
                    "Help me get Fuel by likeing this cast!\n5 Likes = 1 Fuel🔋\nSupport my mech battles in Wreck League Versus 🤖 by @towerecosystem",
                    "Pls help me get Fuel by liking this cast!\n5 Like = 1 Fuel🔋\nSuport my mech battles in Wreck League Versus 🤖 by @towerecosystem", 
                    "Help me get Fuel by likng this cast!\n5 Likes = 1 Fuel🔋\nSupport my mech batles in Wreck League Versus 🤖 by @towerecosystem",
                    "Help me get Fuel by liking this cast pls!\n5 Likes = 1 Fuel🔋\nSupport my mech battles in Wreck League Versus 🤖 by @towerecosystem",
                    "Help me get Fuel by liking this cast!\n5 Likes = 1 Fuel🔋\nSupport my mech battles in Wreck League Versus 🤖 by @towerecosystem thx!",
                    "Hlp me get Fuel by liking this cast!\n5 Likes = 1 Fuel🔋\nSupport my mech battles in Wreck League Versus 🤖 by @towerecosystem",
                    "Help me get Fuel by liking this cast!\n5 likes = 1 fuel🔋\nSupport my mech battles in Wreck League Versus 🤖 by @towerecosystem",
                    "Help me get Fuel by likeing this cast plz!\n5 Likes = 1 Fuel🔋\nSupport my mech battles in Wreck League Versus 🤖 by @towerecosystem"
                ]
                cast_text = random.choice(text_variations)
            
            payload = {
                "text": cast_text,
                "embeds": [f"https://versus.wreckleague.xyz/{self.user_id}"]
            }
            
            print(f"   Text: {cast_text[:50]}...")
            
            cast_response = requests.post(cast_url, headers=cast_headers, json=payload)
            
            if cast_response.status_code in [200, 201]:
                print("   ✅ Cast posted successfully!")
                result = cast_response.json()
                if 'result' in result and 'cast' in result['result']:
                    cast_info = result['result']['cast']
                    print(f"   🆔 Cast hash: {cast_info.get('hash', 'Unknown')}")
                
                print("\n🎉 Share process completed!")
                print("📈 Get likes on your cast to earn fuel!")
                print("💡 Wait a few minutes then check share details!")
                return True
            else:
                print(f"   ❌ Cast failed: {cast_response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Share process failed: {e}")
            return False
    
    def run_auto_vote(self):
        """Menjalankan proses auto vote sekali"""
        print("=" * 60)
        print("STARTING FARCASTER AUTO VOTE PROCESS")
        print("=" * 60)
        
        try:
            # 1. Send mini app event (open)
            print("1. Sending mini app open event...")
            if self.send_mini_app_event("versus.wreckleague.xyz", "open"):
                print("✓ Mini app event sent successfully")
            else:
                print("✗ Failed to send mini app event")
                return False
            
            # 2. Get frame info
            print("2. Getting frame information...")
            frame_info = self.get_frame_info()
            if frame_info:
                print("✓ Frame info retrieved successfully")
            else:
                print("✗ Failed to get frame info")
                return False
            
            # 3. Get user data
            print("3. Getting user data...")
            user_data = self.get_user_data()
            if user_data:
                print("✓ User data retrieved successfully")
                print(f"   User: {user_data.get('username', 'Unknown')}")
            else:
                print("✗ Failed to get user data")
                return False
            
            # 4. Get match details
            print("4. Getting match details...")
            match_details = self.get_match_details()
            if match_details:
                print("✓ Match details retrieved successfully")
                if 'match' in match_details:
                    print(f"   Match ID: {match_details['match'].get('id', 'Unknown')}")
            else:
                print("✗ Failed to get match details")
                return False
            
            # 5. Submit prediction/vote
            print("5. Submitting prediction vote...")
            if self.submit_prediction():
                print("✓ Prediction vote submitted successfully!")
                
                # 6. Send amplitude tracking
                print("6. Sending tracking data...")
                if self.send_amplitude_tracking():
                    print("✓ Tracking data sent successfully")
                else:
                    print("✗ Failed to send tracking data")
                
                return True
            else:
                print("✗ Failed to submit prediction vote")
                return False
                
        except Exception as e:
            print(f"✗ Error in auto vote process: {e}")
            return False

def load_authorization_token(file_path="account.txt"):
    """Load authorization token dari file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            token = f.read().strip()
            if token:
                print(f"✓ Authorization token loaded from {file_path}")
                return token
            else:
                print(f"✗ Empty authorization token in {file_path}")
                return None
    except Exception as e:
        print(f"✗ Error loading authorization token: {e}")
        return None

def load_privy_token():
    """Load privy token dari privy.txt"""
    try:
        with open('privy.txt', 'r') as f:
            token = f.read().strip()
            if token:
                print("✓ Privy token loaded from privy.txt")
                return token
            else:
                print("❌ privy.txt is empty")
                return None
    except FileNotFoundError:
        print("❌ privy.txt not found")
        return None
    except Exception as e:
        print(f"❌ Error reading privy.txt: {e}")
        return None

def main():
    """Main function"""
    print("FARCASTER AUTO VOTE SCRIPT")
    print("=========================")
    
    # Load authorization token dulu
    auth_token = load_authorization_token()
    if not auth_token:
        print("❌ Error: Could not load authorization token!")
        return
    
    # Buat instance sementara untuk deteksi fuel
    temp_bot = FarcasterAutoVote(auth_token, 1, 10, None)
    
    print("\n🔍 Detecting user fuel...")
    current_fuel = temp_bot.get_user_fuel_info()
    if current_fuel > 0:
        print(f"✅ Auto-detected fuel: {current_fuel}")
    else:
        print("⚠️  Could not auto-detect fuel, please input manually")
    
    # Main menu options
    print("\n📋 PILIH AKSI:")
    print("1. Auto Vote Only")
    print("2. Share Process (trigger task + post cast)")
    print("3. Check Fuel Status") 
    print("4. Claim Fuel Reward")
    print("5. Test Different Triggers")
    print("6. Continuous Auto Vote (Loop)")
    print("7. Exit")
    
    action_choice = input("\nPilih aksi (1/2/3/4/5/6/7): ").strip()
    
    if action_choice == "2":
        # Share process
        print("\n🚀 SHARE PROCESS")
        print("=" * 25)
        
        # Load privy token jika perlu
        privy_token = load_privy_token()
        
        # Buat instance untuk share
        share_bot = FarcasterAutoVote(auth_token, 1, 10, None, privy_token)
        
        use_custom = "n"  # Auto-set to no custom text
        custom_text = None
        
        if share_bot.simple_share_process(custom_text):
            print("✅ Share process completed!")
        else:
            print("❌ Share process failed!")
        return
        
    elif action_choice == "3":
        # Check fuel status only
        print("\n📊 FUEL STATUS & SHARE DETAILS")
        print("=" * 35)
        
        print("🔋 Basic Fuel Status:")
        fuel_status = temp_bot.check_fuel_status()
        if fuel_status:
            print(f"📊 Fuel status:")
            import json
            print(json.dumps(fuel_status, indent=2))
        else:
            print("❌ Gagal mendapatkan status fuel")
            
        print("\n📈 Share Details:")
        share_details = temp_bot.check_share_details()
        if share_details:
            print(f"📊 Share details:")
            print(json.dumps(share_details, indent=2))
        else:
            print("❌ Gagal mendapatkan share details")
        return
        
    elif action_choice == "4":
        # Claim fuel only
        print("\n⛽ CLAIM FUEL REWARD")
        print("=" * 30)
        
        fuel_status = temp_bot.check_fuel_status()
        if fuel_status:
            print(f"📊 Current fuel status: {fuel_status}")
        
        confirm = input("\nClaim fuel reward sekarang? (y/n): ").strip().lower()
        if confirm == 'y' or confirm == '':
            if temp_bot.claim_fuel_reward():
                print("✅ Fuel berhasil di-claim!")
            else:
                print("❌ Gagal claim fuel!")
        return
        
    elif action_choice == "5":
        # Test different triggers
        print("\n🔍 TEST DIFFERENT TRIGGERS")
        print("=" * 30)
        
        test_bot = FarcasterAutoVote(auth_token, 1, 10, None)
        working_url, working_method = test_bot.try_different_triggers()
        
        if working_url:
            print(f"\n✅ FOUND WORKING TRIGGER!")
            print(f"URL: {working_url}")
            print(f"Method: {working_method}")
        else:
            print("\n❌ No working trigger found")
        return
        
    elif action_choice == "6":
        # Continuous Auto Vote
        continuous_auto_vote()
        return
        
    elif action_choice == "7":
        print("👋 Goodbye!")
        return
        
    elif action_choice != "1":
        print("❌ Pilihan tidak valid!")
        return
    
    # Lanjut ke konfigurasi voting jika pilih option 1
    print("\n⚙️  KONFIGURASI VOTING:")
    print("1. Blue (Kanan)")
    print("2. Red (Kiri)")
    print("3. Auto")
    
    team_choice_num = "3"  # Auto-select auto mode
    if team_choice_num == "1":
        team_choice = "blue"
        print("✅ Team: Blue (Kanan)")
    elif team_choice_num == "2":
        team_choice = "red"
        print("✅ Team: Red (Kiri)")
    else:
        team_choice = None
        print("✅ Team: Auto")
    
    # Fuel configuration
    if current_fuel > 0:
        use_auto = "y"  # Auto-use detected fuel
        if use_auto == 'y' or use_auto == '':
            max_fuel = current_fuel
            print(f"✅ Using auto-detected fuel: {max_fuel}")
        else:
            max_fuel_input = "5"  # Default fuel
            try:
                max_fuel = int(max_fuel_input)
                if max_fuel <= 0:
                    print("❌ Total fuel harus lebih dari 0!")
                    return
                print(f"✅ Total fuel: {max_fuel}")
            except ValueError:
                print("❌ Input tidak valid!")
                return
    else:
        max_fuel_input = input("\nMasukkan total fuel yang dimiliki: ").strip()
        try:
            max_fuel = int(max_fuel_input)
            if max_fuel <= 0:
                print("❌ Total fuel harus lebih dari 0!")
                return
            print(f"✅ Total fuel: {max_fuel}")
        except ValueError:
            print("❌ Input tidak valid!")
            return
    
    fuel_input = "1"  # Auto-use 1 fuel for vote
    try:
        fuel_amount = int(fuel_input)
        if fuel_amount <= 0:
            print("❌ Fuel untuk vote harus lebih dari 0!")
            return
        elif fuel_amount > max_fuel:
            print(f"❌ Fuel untuk vote ({fuel_amount}) tidak boleh melebihi total fuel ({max_fuel})!")
            return
        print(f"✅ Fuel untuk vote: {fuel_amount}")
    except ValueError:
        print("❌ Input tidak valid!")
        return
    
    # Continuous mode configuration
    print("\n🔄 CONTINUOUS MODE:")
    print("1. Single Vote (Vote sekali lalu stop)")
    print("2. Continuous Loop (Vote terus berdasarkan timing match)")
    
    continuous_choice = "2"  # Auto-select continuous mode
    if continuous_choice == "2":
        continuous_mode = True
        print("✅ Mode: Continuous Loop")
        print("💡 Script akan vote terus berdasarkan timing match")
        print("💡 Press Ctrl+C untuk stop")
    else:
        continuous_mode = False
        print("✅ Mode: Single Vote")
    
    print("\n" + "="*50)
    
    # Initialize auto vote bot dengan konfigurasi
    bot = FarcasterAutoVote(
        authorization_token=auth_token,
        fuel_amount=fuel_amount,
        max_fuel=max_fuel,
        team_preference=team_choice
    )
    
    if continuous_mode:
        # Continuous voting mode
        print("\n🔄 STARTING CONTINUOUS AUTO VOTE")
        print("=" * 50)
        vote_count = 0
        
        try:
            while True:
                vote_count += 1
                print(f"\n🔄 VOTE ATTEMPT #{vote_count}")
                print("=" * 30)
                
                # Check current fuel
                try:
                    temp_bot = FarcasterAutoVote(auth_token, 1, 10, None)
                    fuel_info = temp_bot.get_user_fuel_info()
                    if fuel_info and isinstance(fuel_info, dict) and 'data' in fuel_info:
                        fuel_data = fuel_info['data']
                        if isinstance(fuel_data, dict) and 'data' in fuel_data:
                            current_fuel_check = fuel_data['data'].get('fuelBalance', 0)
                        else:
                            current_fuel_check = 3  # Default fallback
                    else:
                        current_fuel_check = 3  # Default fallback
                        
                    if current_fuel_check < fuel_amount:
                        print(f"❌ Insufficient fuel! Available: {current_fuel_check}, Required: {fuel_amount}")
                        print("⏳ Waiting 5 minutes before checking again...")
                        time.sleep(300)
                        continue
                except Exception as e:
                    print(f"⚠️ Could not check fuel: {e}, using default")
                    current_fuel_check = 3
                
                print(f"⛽ Available fuel: {current_fuel_check}")
                
                # Update bot fuel
                bot.max_fuel = current_fuel_check
                
                # Attempt vote
                print(f"\n🗳️ Starting vote process #{vote_count}...")
                success = bot.run_auto_vote()
                
                if success:
                    print(f"✅ Vote #{vote_count} successful!")
                    
                    # Show timing info
                    try:
                        match_details = bot.get_match_details()
                        if match_details and 'data' in match_details and match_details['data']['matchData']:
                            current_match = match_details['data']['matchData'][0]
                            show_match_timing_info(current_match)
                            
                            # Calculate wait time until next voting window
                            voting_end_str = current_match.get('votingEndTime') or current_match.get('endTime')
                            if voting_end_str:
                                voting_end = parse_iso_time(voting_end_str)
                                now_utc = datetime.datetime.now(pytz.UTC)
                                
                                if voting_end and now_utc < voting_end:
                                    remaining = (voting_end - now_utc).total_seconds()
                                    wait_time = remaining + 120  # Wait until voting ends + 2 minutes
                                    print(f"⏳ Next check in {format_duration(wait_time)}")
                                    print("💤 Waiting for next voting window...")
                                    time.sleep(wait_time)
                                else:
                                    print("⏳ Voting ended, checking for next match in 60 seconds...")
                                    time.sleep(60)
                            else:
                                print("⏳ No timing info, waiting 5 minutes...")
                                time.sleep(300)
                    except Exception as e:
                        print(f"⚠️ Could not get timing info: {e}")
                        time.sleep(300)
                        
                else:
                    print(f"❌ Vote #{vote_count} failed!")
                    print("🔄 Will retry in 2 minutes...")
                    time.sleep(120)
                    
        except KeyboardInterrupt:
            print(f"\n\n⛔ Continuous voting stopped by user")
            print(f"📊 Total vote attempts: {vote_count}")
            print("👋 Goodbye!")
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            print(f"📊 Total vote attempts: {vote_count}")
    else:
        # Single vote mode
        print("\n🗳️  STARTING AUTO VOTE PROCESS")
        print("=" * 40)
        success = bot.run_auto_vote()
        
        if success:
            print("\n🎉 Auto vote process completed successfully!")
            remaining_fuel = max_fuel - fuel_amount
            print(f"💰 Sisa fuel: {remaining_fuel}")
            print(f"💡 Tips: Gunakan menu share untuk claim fuel!")
            print(f"🔗 Your profile: https://versus.wreckleague.xyz/{bot.user_id}")
            
            # Tampilkan informasi timing match
            try:
                match_details = bot.get_match_details()
                if match_details and 'data' in match_details and match_details['data']['matchData']:
                    current_match = match_details['data']['matchData'][0]
                    show_match_timing_info(current_match)
            except Exception as e:
                print(f"⚠️ Could not load timing info: {e}")
                
        else:
            print("\n❌ Auto vote process failed!")
            
            # Tampilkan timing info juga untuk kasus gagal (mungkin voting window tutup)
            try:
                match_details = bot.get_match_details()
                if match_details and 'data' in match_details and match_details['data']['matchData']:
                    current_match = match_details['data']['matchData'][0]
                    show_match_timing_info(current_match)
            except Exception as e:
                print(f"⚠️ Could not load timing info: {e}")

def continuous_auto_vote():
    """Continuous auto vote yang berjalan sesuai timing detection"""
    print("\n🔄 CONTINUOUS AUTO VOTE MODE")
    print("=" * 60)
    print("🎯 Script akan otomatis:")
    print("   • Vote ketika voting window terbuka")
    print("   • Wait sampai voting window selesai")
    print("   • Auto-detect match berikutnya")
    print("   • Loop terus menerus berdasarkan timing")
    print("   • Press Ctrl+C untuk stop")
    print()
    
    vote_count = 0
    
    try:
        while True:
            vote_count += 1
            print(f"\n🔄 VOTE CYCLE #{vote_count}")
            print("=" * 40)
            
            # Load token dan setup
            auth_token = load_authorization_token()
            if not auth_token:
                print("❌ No authorization token found!")
                break
                
            # Auto-detect fuel
            current_fuel = detect_user_fuel(auth_token)
            if current_fuel is None or current_fuel <= 0:
                print("❌ No fuel available for voting!")
                print("⏳ Checking again in 5 minutes...")
                time.sleep(300)
                continue
                
            print(f"⛽ Available fuel: {current_fuel}")
            
            # Setup bot
            bot = FarcasterAutoVote(auth_token, 1, current_fuel, "auto")
            
            # Get current match timing
            match_details = bot.get_match_details()
            if not match_details or 'data' not in match_details or not match_details['data']['matchData']:
                print("⚠️ No match data available, checking again in 1 minute...")
                time.sleep(60)
                continue
                
            current_match = match_details['data']['matchData'][0]
            
            # Parse timing
            voting_start_str = current_match.get('votingStartTime')
            voting_end_str = current_match.get('votingEndTime') or current_match.get('endTime')
            
            if not voting_start_str or not voting_end_str:
                print("⚠️ No voting timing available, checking again in 1 minute...")
                time.sleep(60)
                continue
            
            voting_start = parse_iso_time(voting_start_str)
            voting_end = parse_iso_time(voting_end_str)
            now_utc = datetime.datetime.now(pytz.UTC)
            
            print(f"🕐 Current time: {format_time_wib(now_utc)}")
            print(f"🟢 Voting start: {format_time_wib(voting_start)}")
            print(f"🔴 Voting end: {format_time_wib(voting_end)}")
            
            # Check voting status
            if now_utc < voting_start:
                # Voting belum mulai
                wait_time = (voting_start - now_utc).total_seconds()
                print(f"⏳ Voting starts in {format_duration(wait_time)}")
                print(f"💤 Waiting until voting starts...")
                
                # Wait sampai voting start dengan countdown
                while datetime.datetime.now(pytz.UTC) < voting_start:
                    remaining = (voting_start - datetime.datetime.now(pytz.UTC)).total_seconds()
                    if remaining <= 0:
                        break
                    print(f"⏰ Starting in {format_duration(remaining)}", end='\r')
                    time.sleep(min(30, remaining))
                
                print(f"\n🚀 Voting window opened! Attempting vote...")
                
            elif voting_start <= now_utc <= voting_end:
                # Voting sedang berlangsung
                print("✅ Voting window is currently open!")
                remaining_vote_time = (voting_end - now_utc).total_seconds()
                print(f"⏳ Voting ends in {format_duration(remaining_vote_time)}")
                
            else:
                # Voting sudah selesai
                print("⌛ Current voting window has ended")
                print("🔍 Looking for next match...")
                time.sleep(60)
                continue
            
            # Attempt vote
            print(f"\n🗳️ Attempting vote #{vote_count}...")
            success = bot.run_auto_vote()
            
            if success:
                print(f"✅ Vote #{vote_count} successful!")
                remaining_fuel = current_fuel - 1
                print(f"💰 Remaining fuel: {remaining_fuel}")
                
                # Show timing info
                show_match_timing_info(current_match)
                
                # Calculate wait time until voting ends
                now_utc = datetime.datetime.now(pytz.UTC)
                if now_utc < voting_end:
                    wait_until_end = (voting_end - now_utc).total_seconds()
                    print(f"\n⏳ Waiting {format_duration(wait_until_end)} until voting ends...")
                    print("💤 Sleeping until next voting window...")
                    
                    # Sleep dengan progress indicator
                    sleep_interval = min(60, wait_until_end / 10)  # Update setiap menit atau 10% dari waktu
                    slept = 0
                    while slept < wait_until_end:
                        remaining = wait_until_end - slept
                        print(f"⏰ Next check in {format_duration(remaining)}", end='\r')
                        sleep_time = min(sleep_interval, remaining)
                        time.sleep(sleep_time)
                        slept += sleep_time
                        if remaining <= 0:
                            break
                    
                    print(f"\n🔄 Voting window ended, looking for next match...")
                else:
                    print("🔄 Voting already ended, looking for next match...")
                    
            else:
                print(f"❌ Vote #{vote_count} failed!")
                
                # Show timing info for diagnosis
                show_match_timing_info(current_match)
                
                # If vote failed, might be timing issue
                now_utc = datetime.datetime.now(pytz.UTC)
                if now_utc > voting_end:
                    print("💡 Vote failed because voting window closed")
                    print("🔄 Looking for next voting window...")
                elif now_utc < voting_start:
                    print("💡 Vote failed because voting hasn't started yet")
                    wait_time = (voting_start - now_utc).total_seconds()
                    print(f"⏳ Waiting {format_duration(wait_time)} for voting to start...")
                    time.sleep(wait_time)
                else:
                    print("💡 Vote failed for other reason, retrying in 2 minutes...")
                    time.sleep(120)
                    
            # Small delay before next cycle
            print("\n" + "="*60)
            time.sleep(5)
                
    except KeyboardInterrupt:
        print(f"\n\n⛔ Continuous auto vote stopped by user")
        print(f"📊 Total vote cycles: {vote_count}")
        print("👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Unexpected error in continuous vote: {e}")
        print(f"📊 Total vote cycles: {vote_count}")

if __name__ == "__main__":
    main()
