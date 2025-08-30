#!/usr/bin/env python3
"""
Farcaster Auto Vote Script - Clean Version
Script untuk melakukan otomatisasi vote fuel frame di Farcaster
"""

import requests
import json
import time
import random
import datetime
import signal
import sys
import os
import pytz
import uuid
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import unquote, quote

# Global configuration variables
global_team_preference = "auto"
global_fuel_strategy = "max"
global_min_fuel_threshold = 1

# Color codes for terminal styling
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'

def colored_text(text, color):
    """Add color to text"""
    return f"{color}{text}{Colors.END}"

def print_colored_box(title, content, color=Colors.CYAN):
    """Print content in a colored box"""
    lines = content.split('\n') if isinstance(content, str) else content
    max_length = max(len(line) for line in lines) if lines else 50
    box_width = max(max_length + 4, len(title) + 4, 60)
    
    print(colored_text("┌" + "─" * (box_width - 2) + "┐", color))
    print(colored_text(f"│ {title.center(box_width - 4)} │", color))
    print(colored_text("├" + "─" * (box_width - 2) + "┤", color))
    
    for line in lines:
        padding = box_width - len(line) - 4
        print(colored_text(f"│ {line}{' ' * padding} │", color))
    
    print(colored_text("└" + "─" * (box_width - 2) + "┘", color))

def print_simple_status(message, status="info"):
    """Print simple status message without confusing JSON"""
    colors = {
        "success": Colors.GREEN,
        "error": Colors.RED, 
        "info": Colors.CYAN,
        "warning": Colors.YELLOW
    }
    color = colors.get(status, Colors.WHITE)
    print(f"{colored_text(message, color)}")
    
    print(f"{colored_text('═' * 70, color)}")

def parse_iso_time(iso_string):
    """Parse ISO time string ke datetime object"""
    try:
        # Remove 'Z' dan parse
        if iso_string.endswith('Z'):
            iso_string = iso_string[:-1] + '+00:00'
        dt = datetime.datetime.fromisoformat(iso_string)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.UTC)
        return dt
    except Exception as e:
        print(f"Error parsing time: {e}")
        return None

def format_time_wib(dt):
    """Format datetime ke WIB timezone"""
    try:
        wib = pytz.timezone('Asia/Jakarta')
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.UTC)
        wib_time = dt.astimezone(wib)
        return wib_time.strftime('%Y-%m-%d %H:%M:%S WIB')
    except:
        return str(dt)

def get_voting_timing(match_data):
    """Get voting timing status for a match"""
    try:
        # Simple timing check
        now = datetime.datetime.now(pytz.UTC)
        
        # For now, assume voting is always open if match exists
        # In real implementation, you'd check votingStartTime and votingEndTime
        return {
            'status': 'open',
            'remaining_vote_time': 3600  # 1 hour default
        }
    except Exception as e:
        return {
            'status': 'unknown',
            'remaining_vote_time': 0
        }

def format_duration(seconds):
    """Format duration dalam format yang mudah dibaca"""
    if seconds < 60:
        return f"{int(seconds)} seconds"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes} minutes"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"

def show_match_timing_info(match_data):
    """Tampilkan info timing match dengan deteksi yang lebih akurat"""
    try:
        voting_start_str = match_data.get('votingStartTime')
        voting_end_str = match_data.get('votingEndTime') or match_data.get('endTime')
        
        if voting_start_str and voting_end_str:
            voting_start = parse_iso_time(voting_start_str)
            voting_end = parse_iso_time(voting_end_str)
            now_utc = datetime.datetime.now(pytz.UTC)
            
            print(f"\n⏰ MATCH TIMING INFO:")
            print(f"🕐 Current time: {format_time_wib(now_utc)}")
            print(f"🟢 Voting start: {format_time_wib(voting_start)}")
            print(f"🔴 Voting end: {format_time_wib(voting_end)}")
            
            if now_utc < voting_start:
                wait_time = (voting_start - now_utc).total_seconds()
                print(f"⏳ Voting starts in: {format_duration(wait_time)}")
                return 'waiting', wait_time
            elif voting_start <= now_utc <= voting_end:
                remaining_time = (voting_end - now_utc).total_seconds()
                print(f"✅ Voting is OPEN! Ends in: {format_duration(remaining_time)}")
                return 'open', remaining_time
            else:
                print("⌛ Voting window has CLOSED")
                return 'closed', 0
        else:
            print("⚠️ No timing info available")
            return 'unknown', 0
    except Exception as e:
        print(f"⚠️ Could not parse timing info: {e}")
        return 'error', 0

def wait_for_next_match(bot_instance, max_wait_minutes=30):
    """Wait dan deteksi match baru dengan timing info"""
    print(f"\n🔍 Checking for new match with timing info...")
    
    for attempt in range(max_wait_minutes):
        try:
            print(f"🔄 Attempt {attempt + 1}/{max_wait_minutes} - Checking match status...")
            
            # Get fresh match data
            match_details = bot_instance.get_match_details()
            if not match_details or 'data' not in match_details or not match_details['data']['matchData']:
                print(f"⚠️ No match data available, waiting 1 minute...")
                time.sleep(60)
                continue
            
            current_match = match_details['data']['matchData'][0]
            match_id = current_match.get('_id', 'Unknown')
            
            # Check timing info
            status, wait_time = show_match_timing_info(current_match)
            
            if status == 'waiting':
                print(f"⏳ Found new match {match_id[:10]}... starting in {format_duration(wait_time)}")
                print(f"💤 Waiting until voting starts...")
                
                # Wait dengan countdown yang lebih akurat
                voting_start_str = current_match.get('votingStartTime')
                if voting_start_str:
                    voting_start = parse_iso_time(voting_start_str)
                    
                    while datetime.datetime.now(pytz.UTC) < voting_start:
                        remaining = (voting_start - datetime.datetime.now(pytz.UTC)).total_seconds()
                        if remaining <= 0:
                            break
                        print(f"⏰ Voting starts in {format_duration(remaining)}", end='\r')
                        time.sleep(min(30, remaining))
                    
                    print(f"\n🚀 Voting window opened for match {match_id[:10]}...!")
                    return True, current_match
                
            elif status == 'open':
                print(f"✅ Found active voting window for match {match_id[:10]}...!")
                return True, current_match
            
            elif status == 'closed':
                print(f"⌛ Match {match_id[:10]}... voting ended, looking for next...")
                time.sleep(60)
                continue
                
            else:
                print(f"⚠️ Unknown match status, checking again in 1 minute...")
                time.sleep(60)
                continue
                
        except Exception as e:
            print(f"❌ Error checking match: {e}, retrying in 1 minute...")
            time.sleep(60)
            continue
    
    print(f"❌ Could not find new match after {max_wait_minutes} minutes")
    return False, None

class FarcasterAutoVote:
    def __init__(self, authorization_token, fuel_amount=1, max_fuel=10, team_preference=None):
        self.authorization_token = authorization_token
        self.fuel_amount = fuel_amount
        self.max_fuel = max_fuel
        self.team_preference = team_preference
        self.user_id = None
        
        # Auto-detect FID
        self.user_id = self.detect_fid_from_token()
        if not self.user_id:
            print("⚠️ Could not auto-detect FID")

    def detect_fid_from_token(self):
        """Auto-detect FID dari authorization token"""
        try:
            headers = {
                'authorization': f'Bearer {self.authorization_token}',
                'content-type': 'application/json',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            url = "https://client.warpcast.com/v2/me"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                user_data = data.get('result', {}).get('user', {})
                fid = user_data.get('fid')
                username = user_data.get('username', 'Unknown')
                
                if fid:
                    print(f"✅ Auto-detected FID: {fid} (@{username})")
                    return fid
                    
        except Exception as e:
            print(f"❌ Error detecting FID: {e}")
            
        return None

    def _generate_uuid(self):
        """Generate UUID untuk keperluan API"""
        return str(uuid.uuid4())

    def register_user_to_frame(self):
        """Register user ke Wreck League frame jika belum terdaftar"""
        try:
            # Get user info dari Warpcast API
            headers = {
                'authorization': f'Bearer {self.authorization_token}',
                'content-type': 'application/json',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            url = "https://client.warpcast.com/v2/me"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                print("❌ Could not get user info from Warpcast")
                return False
                
            user_data = response.json().get('result', {}).get('user', {})
            fid = user_data.get('fid')
            username = user_data.get('username')
            display_name = user_data.get('displayName')
            pfp_url = user_data.get('pfp', {}).get('url', '')
            
            if not fid:
                print("❌ Could not extract FID from user data")
                return False
            
            print(f"📝 Registering user to Wreck League frame...")
            print(f"   FID: {fid}")
            print(f"   Username: @{username}")
            print(f"   Display Name: {display_name}")
            
            # Register user ke Wreck League
            register_payload = {
                "user": {
                    "fid": fid,
                    "username": username,
                    "displayName": display_name,
                    "pfpUrl": pfp_url
                },
                "client": {
                    "clientFid": 9152,
                    "added": True,
                    "notificationDetails": {
                        "token": self._generate_uuid(),
                        "url": "https://api.farcaster.xyz/v1/frame-notifications"
                    }
                }
            }
            
            register_url = "https://versus-prod-api.wreckleague.xyz/v1/user/add"
            register_headers = {
                "accept": "*/*",
                "content-type": "application/json",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.post(register_url, 
                                   headers=register_headers, 
                                   json=register_payload, 
                                   timeout=10)
            
            if response.status_code in [200, 201]:
                print("✅ User successfully registered to Wreck League!")
                
                # Setup notification
                notification_payload = {
                    "fid": fid,
                    "clientFid": 9152,
                    "notificationDetails": {
                        "token": self._generate_uuid(),
                        "url": "https://api.farcaster.xyz/v1/frame-notifications"
                    }
                }
                
                notification_url = "https://versus-prod-api.wreckleague.xyz/v1/user/notification"
                requests.post(notification_url, 
                            headers=register_headers, 
                            json=notification_payload, 
                            timeout=5)
                
                return True
            else:
                print(f"{colored_text(f'❌ Registration failed: {response.status_code}', Colors.RED)}")
                return False
                
        except Exception as e:
            print(f"{colored_text(f'❌ Error registering user: {e}', Colors.RED)}")
            return False

    def get_user_fuel_info(self, fid=None):
        """Get accurate fuel info with comprehensive debugging"""
        try:
            fid = fid or self.user_id
            print(f"{colored_text(f'🔍 Checking fuel for FID: {fid}', Colors.CYAN)}")
            
            url = f"https://versus-prod-api.wreckleague.xyz/v1/user/data?fId={fid}"
            headers = {
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "authorization": f"Bearer {self.authorization_token}",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            print(f"{colored_text(f'📡 API Response Status: {response.status_code}', Colors.YELLOW)}")
            
            if response.status_code == 404:
                print(f"{colored_text('❌ User not found, attempting registration...', Colors.RED)}")
                if self.register_user_to_frame():
                    time.sleep(3)
                    response = requests.get(url, headers=headers, timeout=10)
                else:
                    return 0
            
            if response.status_code == 200:
                data = response.json()
                print(f"{colored_text('� Raw API Response Structure:', Colors.CYAN)}")
                print(f"{colored_text('  Response structure will be analyzed below...', Colors.WHITE)}")
                
                # Check for canClaimFuel
                user_data = data.get('data', {}) if isinstance(data, dict) else {}
                can_claim = user_data.get('canClaimFuel', False)
                
                if can_claim:
                    print(f"{colored_text('🎁 Can claim fuel: YES - Auto claiming...', Colors.GREEN)}")
                    if self.claim_fuel_reward():
                        time.sleep(2)
                        response = requests.get(url, headers=headers, timeout=10)
                        if response.status_code == 200:
                            data = response.json()
                            print(f"{colored_text('✅ Data refreshed after fuel claim', Colors.GREEN)}")
                else:
                    print(f"{colored_text('🎁 Can claim fuel: NO', Colors.YELLOW)}")
                
                # Enhanced fuel path detection with better error handling
                fuel_paths = [
                    ['data', 'fuelBalance'],
                    ['data', 'data', 'fuelBalance'],
                    ['data', 'fuel'],
                    ['data', 'data', 'fuel'],
                    ['data', 'user', 'fuel'],
                    ['fuel'],
                    ['fuelBalance'],
                    ['user', 'fuel'],
                    ['data', 'user', 'fuelBalance']
                ]
                
                print(f"{colored_text('🔍 Checking fuel status...', Colors.CYAN)}")
                
                # Try fuel paths without verbose debugging
                for path in fuel_paths:
                    try:
                        fuel_value = data
                        for key in path:
                            if isinstance(fuel_value, dict) and key in fuel_value:
                                fuel_value = fuel_value[key]
                            else:
                                raise KeyError(f"Key '{key}' not found")
                        
                        if isinstance(fuel_value, (int, float)) and fuel_value >= 0:
                            path_str = " -> ".join(path)
                            print(f"{colored_text(f'✅ Found fuel: {fuel_value} (via {path_str})', Colors.GREEN)}")
                            return int(fuel_value)
                            
                    except:
                        continue
                
                # If no fuel found, return 0 quietly
                print(f"{colored_text('❌ No fuel found in account', Colors.RED)}")
                return 0
            else:
                print(f"{colored_text(f'❌ API returned status {response.status_code}', Colors.RED)}")
                print(f"{colored_text(f'Response: {response.text[:200]}', Colors.WHITE)}")
                return 0
            
        except Exception as e:
            print(f"{colored_text(f'❌ Critical error in fuel detection: {e}', Colors.RED)}")
            return 0

    def claim_fuel_reward(self):
        """Claim fuel reward if available"""
        try:
            print(f"{colored_text('⛽ Attempting to claim fuel reward...', Colors.YELLOW)}")
            
            # Get current user data to check rewards
            headers = {
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.9',
                'authorization': f'Bearer {self.authorization_token}',
                'content-type': 'application/json',
                'origin': 'https://warpcast.com',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            # Claim fuel reward
            payload = {"fid": self.user_id}
            response = requests.post(
                "https://versus-prod-api.wreckleague.xyz/v1/user/claim-fuel", 
                headers=headers, 
                json=payload, 
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"{colored_text('✅ Fuel reward claimed successfully!', Colors.GREEN)}")
                return True
            else:
                print(f"{colored_text(f'❌ Failed to claim fuel reward: {response.status_code}', Colors.RED)}")
                return False
                
        except Exception as e:
            print(f"{colored_text(f'❌ Error claiming fuel reward: {e}', Colors.RED)}")
            return False

    def get_best_mech(self, match_id, team_preference=None):
        """Pilih mech terbaik berdasarkan win probability dan preferensi tim"""
        try:
            print(f"{colored_text(f'🤖 Analyzing mechs for match {match_id}...', Colors.CYAN)}")
            
            # Get match details untuk mech list
            match_details = self.get_match_details()
            if not match_details or 'data' not in match_details:
                print(f"{colored_text('❌ Could not get match details', Colors.RED)}")
                return None
            
            # Find mechs in match data
            current_match = match_details['data']['matchData'][0]
            mechs = []
            
            # Simple mech selection logic
            if 'mechs' in current_match:
                mechs = current_match['mechs']
            
            if not mechs:
                print(f"{colored_text('❌ No mechs found in match data', Colors.RED)}")
                return None
            
            # Select best mech (simple: first one with highest win probability)
            best_mech = max(mechs, key=lambda x: x.get('winProbability', 0))
            mech_name = best_mech.get('name', 'Unknown')
            print(f"{colored_text(f'🏆 Selected mech: {mech_name}', Colors.GREEN)}")
            return best_mech
            
        except Exception as e:
            print(f"{colored_text(f'❌ Error in get_best_mech: {e}', Colors.RED)}")
            return None

    def claim_fuel_reward(self):
        """Claim fuel reward jika tersedia"""
        try:
            print(f"⛽ Attempting to claim fuel reward...")
            
            # Endpoint untuk claim fuel reward
            url = f"https://versus-prod-api.wreckleague.xyz/v1/user/fuelReward?fId={self.user_id}"
            
            headers = {
                "Authorization": f"Bearer {self.authorization_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.post(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Fuel reward claimed successfully!")
                if 'fuel' in result:
                    print(f"⛽ New fuel amount: {result['fuel']}")
                elif 'data' in result and 'fuel' in result['data']:
                    print(f"⛽ New fuel amount: {result['data']['fuel']}")
                return True
            else:
                print(f"❌ Failed to claim fuel reward: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"📄 Error details: {error_data}")
                except:
                    print(f"📄 Raw response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error claiming fuel reward: {e}")
            return False

    def get_match_details(self):
        """Mendapatkan detail match terbaru - prioritas endpoint terstable"""
        try:
            # Prioritas endpoint yang paling stabil
            endpoints = [
                f"https://versus-prod-api.wreckleague.xyz/v1/match/details?fId={self.user_id}",
                f"https://versus-prod-api.wreckleague.xyz/v1/analysis?fId={self.user_id}",
                "https://versus-prod-api.wreckleague.xyz/v1/analysis"
            ]
            
            # Headers yang lebih lengkap seperti di script asli
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
            
            print(f"🔍 Getting match details for FID: {self.user_id}")
            
            for i, url in enumerate(endpoints, 1):
                try:
                    print(f"� Trying primary endpoint {i}: {url.split('/')[-1]}")
                    response = requests.get(url, headers=headers, timeout=10)
                    print(f"� Response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        data = response.json()
                        print(f"✅ Match details retrieved successfully from endpoint {i}")
                        return data
                    else:
                        print(f"⚠️ Endpoint {i} returned {response.status_code}")
                        
                except Exception as e:
                    print(f"❌ Endpoint {i} error: {e}")
                    continue
            
            print("❌ All endpoints failed to get match details")
            return None
                
        except Exception as e:
            print(f"❌ Error getting match details: {e}")
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
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
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
                
                # CORRECTED MAPPING:
                # Blue = Index 0 (Team pertama), Red = Index 1 (Team kedua)
                if i == 0:
                    team_indicator = "blue"   # Index 0 = Blue Team
                elif i == 1:
                    team_indicator = "red"    # Index 1 = Red Team
                
                # Cek berdasarkan field mechType jika ada
                if 'mechType' in mech:
                    if mech['mechType'] == 'left':
                        team_indicator = "blue"   # Left = Blue Team
                    elif mech['mechType'] == 'right':
                        team_indicator = "red"    # Right = Red Team
                
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
        
        print(f"🎯 Selected best mech: {best_mech['mechId']}")
        print(f"   Win Probability: {best_mech.get('winningProbability', 0)}%")
        return best_mech

    def submit_prediction(self, fid=None, mech_id=None, match_id=None, fuel_points=None):
        """Submit prediction/vote dengan fuel points dan auto claim fuel"""
        try:
            fid = fid or self.user_id
            
            # Auto check dan claim fuel sebelum voting
            print(f"\n{colored_text('⛽ Checking fuel status before voting...', Colors.YELLOW)}")
            current_fuel = self.get_user_fuel_info()
            print(f"{colored_text(f'💰 Available fuel: {current_fuel}', Colors.GREEN)}")
            
            # Auto-detect latest match ID jika tidak disediakan
            if not match_id:
                print(f"{colored_text('🔍 Auto-detecting latest match ID...', Colors.CYAN)}")
                match_id = self.get_latest_match_id(fid)
                if not match_id:
                    print(f"{colored_text('❌ Could not auto-detect match ID', Colors.RED)}")
                    return False
                print(f"{colored_text(f'✅ Using auto-detected match ID: {match_id}', Colors.GREEN)}")
            
            # Ambil match details untuk data terbaru  
            match_details = self.get_match_details()
            if not match_details or 'data' not in match_details or not match_details['data']['matchData']:
                print(f"{colored_text('❌ No active match found', Colors.RED)}")
                return False

            current_match = match_details['data']['matchData'][0]
            
            # Cek apakah sudah vote - tapi tetap lanjut karena bisa vote tim yang sama
            if current_match.get('isVoted', False):
                print("ℹ️  Previous vote detected, checking if additional vote possible...")
            
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
                            team_info = " (🔴 Tim Merah/Kiri)"  # Index 0 = Merah = Kiri
                        elif mech_index == 1:
                            team_info = " (🔵 Tim Biru/Kanan)"  # Index 1 = Biru = Kanan
                    
                    print(f"🎯 Selected mech {mech_id}{team_info}")
                    
                    # Safely get owner display name
                    owner_name = "Unknown"
                    if 'userData' in selected_mech and 'displayName' in selected_mech['userData']:
                        owner_name = selected_mech['userData']['displayName']
                    elif 'ownerName' in selected_mech:
                        owner_name = selected_mech['ownerName']
                    
                    print(f"   👤 Owner: {owner_name}")
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
                    # Cek apakah fuel amount tidak melebihi max fuel dan available fuel
                    max_usable = min(self.fuel_amount, self.max_fuel, current_fuel)
                    fuel_points = max_usable
                else:
                    # Max strategy - gunakan semua fuel yang tersedia
                    fuel_points = min(current_fuel, self.max_fuel)
                
                print(f"🎯 Fuel strategy: {'Custom/Conservative' if self.fuel_amount else 'Max Available'}")
                print(f"💰 Current fuel: {current_fuel}, Max fuel: {self.max_fuel}")
                print(f"⛽ Will use: {fuel_points} fuel points")
            
            # Cek apakah fuel cukup setelah auto claim
            if current_fuel < fuel_points:
                print(f"❌ Insufficient fuel! Need {fuel_points}, have {current_fuel}")
                return False
            
            print(f"⛽ Using {fuel_points} fuel points for vote")
            
            # Payload untuk submit prediction
            payload = {
                "fId": int(fid),
                "mechId": str(mech_id),
                "matchId": str(match_id),
                "fuelPoints": int(fuel_points)
            }
            
            # Submit prediction
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
            
            print(f"\n{colored_text('🚀 Submitting prediction to blockchain...', Colors.BOLD + Colors.CYAN)}")
            
            # Create a beautiful prediction info box
            pred_info = [
                f"👤 FID: {fid}",
                f"🤖 Mech ID: {mech_id}",
                f"🎯 Match ID: {match_id[:10]}...{match_id[-10:]}",
                f"⛽ Fuel Points: {fuel_points}"
            ]
            
            print_colored_box("PREDICTION DETAILS", pred_info, Colors.CYAN)
            
            response = requests.put(url, headers=headers, json=payload, timeout=10)
            
            print(f"📡 API Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print_simple_status("🎉 Prediction submitted successfully! 🎯", "success")
                return True
            else:
                try:
                    error_data = response.json()
                    if 'message' in error_data:
                        print_simple_status(f"❌ Error: {error_data['message']}", "error")
                    else:
                        print_simple_status(f"❌ Vote failed with status {response.status_code}", "error")
                except:
                    print_simple_status(f"❌ Vote failed: {response.text[:100]}...", "error")
                return False
                
        except Exception as e:
            print(f"❌ Error submitting prediction: {e}")
            return False

    def run_auto_vote(self):
        """Main function untuk auto vote"""
        try:
            print(f"{colored_text('🚀 Starting auto vote process...', Colors.BOLD + Colors.CYAN)}")
            print(f"{colored_text(f'👤 User FID: {self.user_id}', Colors.YELLOW)}")
            print(f"{colored_text(f'⛽ Fuel amount: {self.fuel_amount}', Colors.GREEN)}")
            team_pref = self.team_preference or "Auto"
            print(f"{colored_text(f'🎯 Team preference: {team_pref}', Colors.MAGENTA)}")
            
            # Initialize vote counter
            self.votes_submitted = 0
            
            # Get match details
            match_details = self.get_match_details()
            if not match_details:
                print(f"{colored_text('❌ Could not get match details', Colors.RED)}")
                return False
            
            # Get timing info
            if 'data' in match_details and match_details['data'].get('matchData'):
                current_match = match_details['data']['matchData'][0]
            
            # Submit prediction (actual voting)
            print(f"\n🗳️ Executing vote...")
            success = self.submit_prediction()
            
            if success:
                self.votes_submitted = 1  # Track successful vote
                print(f"{colored_text('🎉 Vote submitted successfully! 🎯', Colors.BOLD + Colors.GREEN)}")
                return True
            else:
                print(f"{colored_text('❌ Vote submission failed!', Colors.RED)}")
                return False
                
        except Exception as e:
            print(f"{colored_text(f'❌ Error in auto vote: {e}', Colors.RED)}")
            return False

def load_authorization_token(file_path="account.txt"):
    """Load multiple authorization tokens dari file"""
    try:
        tokens = []
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in lines:
                    token = line.strip()
                    if token and token.startswith('MK-'):
                        tokens.append(token)
            
            if tokens:
                print(f"✅ Loaded {len(tokens)} authorization token(s)")
                return tokens
            else:
                print(f"❌ No valid tokens found in {file_path}")
                return []
        else:
            print(f"❌ File {file_path} not found!")
            return []
    except Exception as e:
        print(f"❌ Error loading tokens: {e}")
        return []

def process_single_account_vote(account_info, team_preference, fuel_strategy, custom_fuel, results_queue):
    """Process single account voting in thread"""
    try:
        account_index = account_info['index']
        token = account_info['token']
        fid = account_info['fid']
        
        print(f"🔄 [Thread-{account_index}] Starting vote process for Account {account_index} (FID: {fid})")
        
        # Initialize bot instance
        fuel_amount = custom_fuel if fuel_strategy == "custom" else None
        bot = FarcasterAutoVote(token, fuel_amount, 10, team_preference)
        
        # Run voting process
        success = bot.run_auto_vote()
        
        # Get actual vote count from bot
        votes_count = getattr(bot, 'votes_submitted', 0) if success else 0
        
        result = {
            'account_index': account_index,
            'fid': fid,
            'success': success,
            'votes_count': votes_count
        }
        
        results_queue.put(result)
        vote_status = f"Success ({votes_count} votes)" if success else "Failed"
        print(f"✅ [Thread-{account_index}] Account {account_index} voting completed: {vote_status}")
        
        return result
        
    except Exception as e:
        error_result = {
            'account_index': account_info['index'],
            'fid': account_info['fid'],
            'success': False,
            'error': str(e),
            'votes_count': 0
        }
        results_queue.put(error_result)
        print(f"❌ [Thread-{account_info['index']}] Error in account {account_info['index']}: {e}")
        return error_result

def run_account_continuous_thread(account_info, thread_id, delay_config=None, team_preference="auto", fuel_strategy="max", min_fuel_threshold=1):
    """Run continuous voting untuk satu akun dalam thread terpisah dengan enhanced match detection"""
    try:
        account = account_info[thread_id]
        fid = account['fid']
        token = account['token']
        fuel = account['fuel']
        
        # Set unique random seed per thread untuk independent delays
        import time
        thread_seed = int(time.time() * 1000000) + thread_id * 1000 + account['index'] * 100
        random.seed(thread_seed)
        print(f"🎲 [Thread-{thread_id+1}] Initialized independent random seed: {thread_seed}")
        
        # Get delay configuration atau gunakan default
        if delay_config:
            min_delay = delay_config.get('min_delay', 30)
            max_delay = delay_config.get('max_delay', 300)
        else:
            min_delay, max_delay = 30, 300  # Default threading delay
        
        print(f"\n🧵 [Thread-{thread_id+1}] Starting continuous voting for Account {account['index']} (FID: {fid})")
        print(f"{colored_text(f'🎲 [Thread-{thread_id+1}] Delay config: {format_duration(min_delay)} - {format_duration(max_delay)} (for continuous mode)', Colors.MAGENTA)}")
        
        # Initialize bot untuk account ini dengan konfigurasi global
        # Team preference conversion: "auto" -> None for FarcasterAutoVote
        bot_team_pref = None if team_preference == "auto" else team_preference
        
        # Create bot dengan fuel_amount = None untuk max strategy (akan detect real-time)
        bot = FarcasterAutoVote(token, None, 10, bot_team_pref)
        
        print(f"🎯 [Thread-{thread_id+1}] Fuel strategy: {fuel_strategy}")
        print(f"⛽ [Thread-{thread_id+1}] Min fuel threshold: {min_fuel_threshold}")
        
        account_cycle_count = 0  # INDEPENDENT cycle counter per account
        last_match_id = None  # Track match ID untuk deteksi match baru
        is_first_vote = True  # Flag untuk voting pertama (no delay)
        vote_delay_seconds = 0  # Default no delay untuk vote pertama
        
        while True:  # Continuous loop untuk account ini
            try:
                account_cycle_count += 1  # Independent counter
                
                # Real-time fuel detection untuk setiap voting cycle
                current_account_fuel = bot.get_user_fuel_info()
                print(f"\n💰 [Account-{account['index']}] Current fuel: {current_account_fuel}")
                
                # Determine fuel amount per cycle berdasarkan strategy dan fuel aktual
                if fuel_strategy == "conservative":
                    if current_account_fuel >= min_fuel_threshold:
                        vote_fuel_amount = min_fuel_threshold
                    else:
                        print(f"⚠️ [Account-{account['index']}] Insufficient fuel for conservative strategy (need {min_fuel_threshold}, have {current_account_fuel})")
                        time.sleep(300)  # Wait 5 minutes and check again
                        continue
                elif fuel_strategy == "custom":
                    if current_account_fuel >= min_fuel_threshold:
                        vote_fuel_amount = min_fuel_threshold
                    else:
                        print(f"⚠️ [Account-{account['index']}] Insufficient fuel for custom strategy (need {min_fuel_threshold}, have {current_account_fuel})")
                        time.sleep(300)  # Wait 5 minutes and check again
                        continue
                else:  # max strategy
                    if current_account_fuel >= min_fuel_threshold:
                        vote_fuel_amount = current_account_fuel  # Use ALL available fuel
                        print(f"🚀 [Account-{account['index']}] Max strategy: Will use ALL {vote_fuel_amount} fuel!")
                    else:
                        print(f"⚠️ [Account-{account['index']}] Insufficient fuel for max strategy (need min {min_fuel_threshold}, have {current_account_fuel})")
                        time.sleep(300)  # Wait 5 minutes and check again
                        continue
                
                # Update bot dengan fuel amount yang benar untuk cycle ini
                bot.fuel_amount = vote_fuel_amount
                
                print(f"\n{colored_text('╔' + '═' * 68 + '╗', Colors.MAGENTA)}")
                thread_text = f"🔄 [Account-{account['index']}] Personal Cycle #{account_cycle_count} (FID: {fid})"
                print(f"{colored_text('║', Colors.MAGENTA)} {colored_text(thread_text, Colors.BOLD + Colors.WHITE):>60} {colored_text('║', Colors.MAGENTA)}")
                print(f"{colored_text('╚' + '═' * 68 + '╝', Colors.MAGENTA)}")
                
                current_fuel = bot.get_user_fuel_info()
                print(f"{colored_text(f'⛽ [Account-{account['index']}] Current fuel: {current_fuel}', Colors.GREEN)}")
                
                # Get match details
                match_details = bot.get_match_details()
                if not match_details or 'data' not in match_details or not match_details['data']['matchData']:
                    print(f"{colored_text(f'❌ [Account-{account['index']}] No active match found, waiting 2 minutes...', Colors.RED)}")
                    time.sleep(120)
                    continue
                
                current_match = match_details['data']['matchData'][0]
                match_id = current_match.get('_id', 'Unknown')
                
                # Check if this is a new match
                if last_match_id != match_id:
                    print(f"{colored_text(f'🆕 [Account-{account['index']}] New match detected: {match_id[:10]}...', Colors.GREEN)}")
                    last_match_id = match_id
                    
                    if is_first_vote:
                        # Voting pertama - TANPA delay
                        vote_delay_seconds = 0
                        print(f"{colored_text(f'🚀 [Account-{account['index']}] First vote - NO DELAY (immediate voting)', Colors.GREEN)}")
                        is_first_vote = False
                    else:
                        # Continuous voting - DENGAN delay random
                        vote_delay_seconds = random.randint(min_delay, max_delay)
                        print(f"{colored_text(f'🎲 [Account-{account['index']}] Continuous mode delay: {format_duration(vote_delay_seconds)} after voting starts', Colors.MAGENTA)}")
                
                # PROPER timing detection dan handling
                status, remaining_time = show_match_timing_info(current_match)
                print(f"{colored_text(f'📊 [Account-{account['index']}] Match Status: {status.upper()}', Colors.CYAN)}")
                
                if status == 'waiting':
                    print(f"{colored_text(f'⏳ [Thread-{thread_id+1}] Voting not started yet, waiting {format_duration(remaining_time)}...', Colors.YELLOW)}")
                    
                    # Wait dengan countdown yang akurat
                    voting_start_str = current_match.get('votingStartTime')
                    if voting_start_str:
                        voting_start = parse_iso_time(voting_start_str)
                        
                        while datetime.datetime.now(pytz.UTC) < voting_start:
                            remaining = (voting_start - datetime.datetime.now(pytz.UTC)).total_seconds()
                            if remaining <= 0:
                                break
                            print(f"{colored_text(f'⏰ [Thread-{thread_id+1}] Voting starts in {format_duration(remaining)}', Colors.CYAN)}", end='\r')
                            time.sleep(min(30, remaining))
                        
                        print(f"\n{colored_text(f'🚀 [Thread-{thread_id+1}] Voting window opened!', Colors.GREEN)}")
                        
                        # Apply delay logic berdasarkan first vote atau continuous
                        if vote_delay_seconds > 0:
                            print(f"{colored_text(f'🎲 [Thread-{thread_id+1}] Waiting random delay {format_duration(vote_delay_seconds)} before voting...', Colors.MAGENTA)}")
                            
                            # Countdown untuk random delay
                            delay_remaining = vote_delay_seconds
                            while delay_remaining > 0:
                                print(f"{colored_text(f'⏳ [Thread-{thread_id+1}] Voting in {format_duration(delay_remaining)}', Colors.YELLOW)}", end='\r')
                                sleep_time = min(10, delay_remaining)  # Update setiap 10 detik
                                time.sleep(sleep_time)
                                delay_remaining -= sleep_time
                            
                            print(f"\n{colored_text(f'🎯 [Thread-{thread_id+1}] Random delay finished, voting now!', Colors.GREEN)}")
                        else:
                            print(f"{colored_text(f'🎯 [Thread-{thread_id+1}] No delay - voting immediately!', Colors.GREEN)}")
                    
                elif status == 'open':
                    print(f"{colored_text(f'✅ [Thread-{thread_id+1}] Voting is open!', Colors.GREEN)}")
                    
                    # Check berapa lama voting sudah berjalan dan apply delay logic
                    voting_start_str = current_match.get('votingStartTime')
                    if voting_start_str and vote_delay_seconds > 0:
                        voting_start = parse_iso_time(voting_start_str)
                        now_utc = datetime.datetime.now(pytz.UTC)
                        time_since_start = (now_utc - voting_start).total_seconds()
                        
                        if time_since_start < vote_delay_seconds:
                            # Masih dalam periode delay, tunggu sisa delay
                            remaining_delay = vote_delay_seconds - time_since_start
                            print(f"{colored_text(f'🎲 [Thread-{thread_id+1}] Waiting remaining delay {format_duration(remaining_delay)}...', Colors.MAGENTA)}")
                            
                            while remaining_delay > 0:
                                print(f"{colored_text(f'⏳ [Thread-{thread_id+1}] Voting in {format_duration(remaining_delay)}', Colors.YELLOW)}", end='\r')
                                sleep_time = min(10, remaining_delay)
                                time.sleep(sleep_time)
                                remaining_delay -= sleep_time
                            
                            print(f"\n{colored_text(f'🎯 [Thread-{thread_id+1}] Random delay finished, voting now!', Colors.GREEN)}")
                        else:
                            print(f"{colored_text(f'🎯 [Thread-{thread_id+1}] Delay period passed, voting immediately!', Colors.GREEN)}")
                    else:
                        print(f"{colored_text(f'🎯 [Thread-{thread_id+1}] No delay - voting immediately!', Colors.GREEN)}")
                    
                    # Try to vote setelah delay
                    success = bot.submit_prediction()
                    
                    if success:
                        print(f"{colored_text(f'🎉 [Account-{account['index']}] Vote submitted successfully! 🎯', Colors.BOLD + Colors.GREEN)}")
                        
                        # PROPER WAIT sampai voting ends dengan timing detection yang akurat
                        print(f"{colored_text(f'⏳ [Account-{account['index']}] Now waiting until voting window completely ends...', Colors.YELLOW)}")
                        
                        voting_end_str = current_match.get('votingEndTime') or current_match.get('endTime')
                        if voting_end_str:
                            voting_end = parse_iso_time(voting_end_str)
                            
                            # Real-time countdown sampai voting berakhir
                            while datetime.datetime.now(pytz.UTC) < voting_end:
                                remaining = (voting_end - datetime.datetime.now(pytz.UTC)).total_seconds()
                                if remaining <= 0:
                                    break
                                print(f"{colored_text(f'⏰ [Account-{account['index']}] Voting ends in {format_duration(remaining)}', Colors.CYAN)}")
                                time.sleep(min(30, remaining))
                            
                            print(f"\n{colored_text(f'✅ [Account-{account['index']}] Voting window ended! Searching for next match...', Colors.BLUE)}")
                            
                            # Wait for next match dengan proper detection
                            print(f"{colored_text(f'🔍 [Account-{account['index']}] Intelligent next match detection...', Colors.CYAN)}")
                            found_new_match, new_match_data = wait_for_next_match(bot, max_wait_minutes=30)
                            
                            if found_new_match:
                                print(f"{colored_text(f'🎉 [Account-{account['index']}] Next match detected! Starting new personal cycle...', Colors.GREEN)}")
                                last_match_id = None  # Reset untuk force detection match baru
                                continue  # Langsung ke cycle berikutnya tanpa delay
                            else:
                                print(f"{colored_text(f'⚠️ [Account-{account['index']}] No next match found within 30 minutes, waiting 5 minutes before retry...', Colors.YELLOW)}")
                                time.sleep(300)
                        else:
                            print(f"{colored_text(f'⚠️ [Account-{account['index']}] Could not get voting end time, waiting 5 minutes...', Colors.YELLOW)}")
                            time.sleep(300)
                    else:
                        print(f"{colored_text(f'❌ [Account-{account['index']}] Vote failed, waiting 2 minutes before retry...', Colors.RED)}")
                        time.sleep(120)
                        
                elif status == 'closed':
                    print(f"{colored_text(f'⌛ [Account-{account['index']}] Voting window has closed, searching for next match...', Colors.BLUE)}")
                    
                    # Wait for next match dengan intelligent detection
                    print(f"{colored_text(f'🔍 [Account-{account['index']}] Intelligent next match detection...', Colors.CYAN)}")
                    found_new_match, new_match_data = wait_for_next_match(bot, max_wait_minutes=30)
                    
                    if found_new_match:
                        print(f"{colored_text(f'🎉 [Account-{account['index']}] Next match detected! Starting new personal cycle...', Colors.GREEN)}")
                        last_match_id = None  # Reset untuk force detection match baru
                        continue  # Langsung ke cycle berikutnya
                    else:
                        print(f"{colored_text(f'⚠️ [Account-{account['index']}] No next match found within 30 minutes, waiting 5 minutes...', Colors.YELLOW)}")
                        time.sleep(300)
                    
                else:
                    print(f"{colored_text(f'⚠️ [Account-{account['index']}] Unknown timing status: {status}, waiting 2 minutes...', Colors.YELLOW)}")
                    time.sleep(120)
                    
                # Small delay before next cycle check (hanya jika tidak continue)
                time.sleep(5)
                
            except Exception as e:
                print(f"{colored_text(f'❌ [Account-{account['index']}] Error in personal cycle #{account_cycle_count}: {e}', Colors.RED)}")
                time.sleep(60)  # Wait 1 minute on error
                
    except KeyboardInterrupt:
        account_index = account.get('index', 'Unknown')
        print(f"\n{colored_text(f'⛔ [Account-{account_index}] Personal thread stopped by user after {account_cycle_count} cycles', Colors.BOLD + Colors.RED)}")
        # Force exit thread
        import os
        os._exit(0)
    except Exception as e:
        print(f"\n{colored_text(f'❌ [Account-{account['index']}] Personal thread error: {e}', Colors.RED)}")
        # Force exit thread on critical error
        import os
        os._exit(1)

def threaded_continuous_multi_account_vote(active_accounts, delay_config=None, team_preference="auto", fuel_strategy="max", min_fuel_threshold=1):
    """Run multi-account voting dengan threading - setiap akun punya continuous loop sendiri"""
    import threading
    
    print(f"\n🧵 Starting threaded continuous voting for {len(active_accounts)} accounts...")
    print("⚠️  Each account will run in its own continuous loop")
    print("⚠️  Press Ctrl+C to stop all threads")
    
    # Show delay configuration
    if delay_config:
        min_delay = delay_config.get('min_delay', 30)
        max_delay = delay_config.get('max_delay', 300)
        print(f"🎲 Random delay range: {format_duration(min_delay)} - {format_duration(max_delay)}")
    
    threads = []
    
    try:
        # Create dan start thread untuk setiap account
        for i, account in enumerate(active_accounts):
            thread = threading.Thread(
                target=run_account_continuous_thread,
                args=(active_accounts, i, delay_config, team_preference, fuel_strategy, min_fuel_threshold),
                daemon=False,  # Changed to False agar bisa di-interrupt
                name=f"Account-{account['index']}-Thread"
            )
            threads.append(thread)
            thread.start()
            print(f"🧵 Started thread for Account {account['index']} (FID: {account['fid']})")
            time.sleep(2)  # Delay antar thread start
        
        print(f"\n✅ All {len(threads)} threads started successfully!")
        print("🔄 Threads are running continuously...")
        print("⛔ Press Ctrl+C to stop all threads")
        
        # Wait for all threads dengan interrupt handling
        try:
            while any(thread.is_alive() for thread in threads):
                time.sleep(0.5)  # Check every 0.5 seconds
        except KeyboardInterrupt:
            print(f"\n\n⛔ Ctrl+C detected! Stopping all threads...")
            # Force terminate semua threads
            import os
            import signal
            os.kill(os.getpid(), signal.SIGTERM)
            
    except KeyboardInterrupt:
        print(f"\n\n⛔ Threaded multi-account voting stopped by user")
        print("👋 All threads will be terminated...")
        # Force exit
        import os
        os._exit(0)
    except Exception as e:
        print(f"\n❌ Threading error: {e}")
        import os
        os._exit(1)

def threaded_multi_account_vote(account_info_list, use_threading=False, delay_config=None):
    """Multi-account voting dengan opsi threading"""
    print(f"\n🚀 Starting {'threaded' if use_threading else 'sequential'} multi-account voting...")
    print("=" * 60)
    print("🎯 Script akan otomatis:")
    print("   • Vote semua account ketika voting window terbuka")
    print("   • Wait sampai voting window selesai")
    print("   • Auto-detect match berikutnya")
    print("   • Loop terus menerus berdasarkan timing")
    print("   • Press Ctrl+C untuk stop")
    print(f"📊 Total accounts: {len(account_info_list)}")
    
    # Filter account yang punya fuel
    active_accounts = [acc for acc in account_info_list if acc['fuel'] > 0]
    if not active_accounts:
        print("❌ No accounts with fuel available!")
        return
    
    print(f"⛽ Active accounts with fuel: {len(active_accounts)}")
    for acc in active_accounts:
        print(f"   Account {acc['index']} (FID: {acc['fid']}): {acc['fuel']} fuel")
    
    # Use active accounts for processing
    account_info_list = active_accounts
    
    # Use global configuration instead of asking user
    print(f"\n{colored_text('🎯 Using global team preference:', Colors.YELLOW)} {colored_text(global_team_preference.title(), Colors.CYAN)}")
    print(f"{colored_text('⛽ Using global fuel strategy:', Colors.YELLOW)} {colored_text(global_fuel_strategy.title(), Colors.CYAN)} (min: {global_min_fuel_threshold})")
    
    vote_cycle = 0
    
    try:
        while True:
            vote_cycle += 1
            
            # Beautiful cycle header
            print(f"\n{colored_text('╔' + '═' * 68 + '╗', Colors.CYAN)}")
            print(f"{colored_text('║', Colors.CYAN)} {colored_text(f'🔄 VOTE CYCLE #{vote_cycle}', Colors.BOLD + Colors.WHITE):>40} {colored_text('║', Colors.CYAN)}")
            current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"{colored_text('║', Colors.CYAN)} {colored_text(f'⏰ {current_time}', Colors.YELLOW):>50} {colored_text('║', Colors.CYAN)}")
            print(f"{colored_text('╚' + '═' * 68 + '╝', Colors.CYAN)}")
            
            if use_threading:
                # Threading approach
                print(f"\n{colored_text('┌─ Threading Info ─' + '─' * 48 + '┐', Colors.MAGENTA)}")
                threading_msg = f'🧵 Using threaded execution for {len(account_info_list)} accounts...'
                print(f"{colored_text('│', Colors.MAGENTA)} {colored_text(threading_msg, Colors.WHITE):<60} {colored_text('│', Colors.MAGENTA)}")
                print(f"{colored_text('└' + '─' * 68 + '┘', Colors.MAGENTA)}")
                results_queue = queue.Queue()
                
                with ThreadPoolExecutor(max_workers=len(account_info_list)) as executor:
                    # Submit all tasks
                    future_to_account = {
                        executor.submit(process_single_account_vote, acc_info, global_team_preference, global_fuel_strategy, global_min_fuel_threshold, results_queue): acc_info
                        for acc_info in account_info_list
                    }
                    
                    # Wait for completion
                    for future in as_completed(future_to_account):
                        account_info = future_to_account[future]
                        try:
                            result = future.result()
                        except Exception as exc:
                            account_index = account_info.get('index', 'Unknown')
                            print(f"{colored_text(f'❌ [Thread] Account {account_index} generated an exception: {exc}', Colors.RED)}")
                
                # Collect results
                all_results = []
                while not results_queue.empty():
                    all_results.append(results_queue.get())
                    
            else:
                # Sequential approach  
                print(f"\n{colored_text('┌─ Sequential Mode ─' + '─' * 47 + '┐', Colors.BLUE)}")
                print(f"{colored_text('│', Colors.BLUE)} {colored_text(f'🔄 Using sequential execution for {len(account_info_list)} accounts...', Colors.WHITE):<60} {colored_text('│', Colors.BLUE)}")
                print(f"{colored_text('└' + '─' * 68 + '┘', Colors.BLUE)}")
                all_results = []
                results_queue = queue.Queue()
                
                for acc_info in account_info_list:
                    result = process_single_account_vote(acc_info, global_team_preference, global_fuel_strategy, global_min_fuel_threshold, results_queue)
                    all_results.append(result)
            
                # Summary results
                successful_votes = sum(1 for r in all_results if r['success'])
                total_votes = sum(r.get('votes_count', 0) for r in all_results)
                
                print(f"\n{colored_text('╔' + '═' * 68 + '╗', Colors.MAGENTA)}")
                print(f"{colored_text('║', Colors.MAGENTA)} {colored_text(f'📊 CYCLE #{vote_cycle} SUMMARY', Colors.BOLD + Colors.WHITE):>50} {colored_text('║', Colors.MAGENTA)}")
                print(f"{colored_text('╚' + '═' * 68 + '╝', Colors.MAGENTA)}")
                print(f"{colored_text(f'✅ Successful accounts: {successful_votes}/{len(account_info_list)}', Colors.GREEN)}")
                print(f"{colored_text(f'🗳️  Total votes submitted: {total_votes}', Colors.CYAN)}")
                
                # Detail per account dengan border
                print(f"\n{colored_text('┌─ Account Details ─' + '─' * 47 + '┐', Colors.YELLOW)}")
                for result in sorted(all_results, key=lambda x: x['account_index']):
                    status_color = Colors.GREEN if result['success'] else Colors.RED
                    status = "✅ Success" if result['success'] else "❌ Failed"
                    votes = result.get('votes_count', 0)
                    error = f" - {result.get('error', '')}" if 'error' in result else ""
                    account_line = f"Account {result['account_index']} (FID: {result['fid']}): {status} ({votes} votes){error}"
                    print(f"{colored_text('│', Colors.YELLOW)} {colored_text(account_line, status_color):<60} {colored_text('│', Colors.YELLOW)}")
                print(f"{colored_text('└' + '─' * 68 + '┘', Colors.YELLOW)}")
                
                if successful_votes > 0:
                    # Get timing info from first successful account dengan deteksi yang lebih baik
                    try:
                        first_successful_token = next(acc['token'] for acc in account_info_list 
                                                    if any(r['account_index'] == acc['index'] and r['success'] for r in all_results))
                        temp_bot = FarcasterAutoVote(first_successful_token, 1, 10, None)
                        match_details = temp_bot.get_match_details()
                        
                        if match_details and 'data' in match_details and match_details['data']['matchData']:
                            current_match = match_details['data']['matchData'][0]
                            
                            # Show timing info dan get status
                            status, remaining_time = show_match_timing_info(current_match)
                            
                            if status == 'open' and remaining_time > 0:
                                print(f"\n⏳ Waiting {format_duration(remaining_time)} until voting ends...")
                                print("💤 All accounts voted, sleeping until next voting window...")
                                
                                # Sleep dengan countdown yang akurat
                                voting_end_str = current_match.get('votingEndTime') or current_match.get('endTime')
                                if voting_end_str:
                                    voting_end = parse_iso_time(voting_end_str)
                                    
                                    while datetime.datetime.now(pytz.UTC) < voting_end:
                                        remaining = (voting_end - datetime.datetime.now(pytz.UTC)).total_seconds()
                                        if remaining <= 0:
                                            break
                                        print(f"⏰ Voting ends in {format_duration(remaining)}", end='\r')
                                        time.sleep(min(30, remaining))
                                
                                print(f"\n🔄 Voting window ended, looking for next match...")
                            
                            # Wait for next match dengan deteksi timing yang akurat
                            print(f"\n{colored_text('🔍 NEXT MATCH DETECTION', Colors.BOLD + Colors.BLUE)}")
                            print(f"{colored_text('⚡ Starting intelligent match detection...', Colors.CYAN)}")
                            
                            # Wait dan deteksi match berikutnya
                            found_new_match, new_match_data = wait_for_next_match(temp_bot, max_wait_minutes=30)
                            
                            if found_new_match and new_match_data:
                                print(f"{colored_text('🎉 New match detected! Continuing with next cycle...', Colors.GREEN)}")
                            else:
                                print(f"{colored_text('⚠️ No new match found, waiting 5 minutes before retry...', Colors.YELLOW)}")
                                time.sleep(300)
                        else:
                            print("⚠️  Could not get match details, waiting 2 minutes...")
                            time.sleep(120)
                            
                    except Exception as e:
                        print(f"⚠️  Error getting timing info: {e}, waiting 2 minutes...")
                        time.sleep(120)
                else:
                    print("💡 All votes failed, checking again in 2 minutes...")
                    time.sleep(120)            # Small delay before next cycle
            print("\n" + "="*60)
            time.sleep(5)
                
    except KeyboardInterrupt:
        print(f"\n\n⛔ {'Threaded' if use_threading else 'Sequential'} multi-account auto vote stopped by user")
        print(f"📊 Total vote cycles: {vote_cycle}")
        print("👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Unexpected error in {'threaded' if use_threading else 'sequential'} vote: {e}")
        print(f"📊 Total vote cycles: {vote_cycle}")

def continuous_multi_account_vote(account_info, delay_config=None, team_preference="auto", fuel_strategy="max", min_fuel_threshold=1):
    """Continuous auto vote untuk multi account dengan match timing"""
    print("\n🔄 CONTINUOUS MULTI-ACCOUNT AUTO VOTE MODE")
    print("=" * 60)
    print("🎯 Script akan otomatis:")
    print("   • Vote semua account ketika voting window terbuka")
    print("   • Wait sampai voting window selesai")
    print("   • Auto-detect match berikutnya")
    print("   • Loop terus menerus berdasarkan timing")
    print("   • Press Ctrl+C untuk stop")
    print(f"📊 Total accounts: {len(account_info)}")
    
    # Get delay configuration atau gunakan default
    if delay_config:
        min_delay = delay_config.get('min_delay', 5)
        max_delay = delay_config.get('max_delay', 180)
        print(f"🎲 Custom delay range: {format_duration(min_delay)} - {format_duration(max_delay)}")
    else:
        min_delay, max_delay = 5, 180  # Default sequential delay
    
    # Filter account yang punya fuel
    active_accounts = [acc for acc in account_info if acc['fuel'] > 0]
    if not active_accounts:
        print("❌ No accounts with fuel available!")
        return
    
    print(f"⛽ Active accounts with fuel: {len(active_accounts)}")
    for acc in active_accounts:
        print(f"   • Account {acc['index']} (FID: {acc['fid']}): {acc['fuel']} fuel")
    
    # Use global configuration instead of asking user
    print(f"\n{colored_text('🎯 Using global team preference:', Colors.YELLOW)} {colored_text(team_preference.title(), Colors.CYAN)}")
    print(f"{colored_text('⛽ Using global fuel strategy:', Colors.YELLOW)} {colored_text(fuel_strategy.title(), Colors.CYAN)} (min: {min_fuel_threshold})")
    
    print(f"\n✅ CONFIGURATION SUMMARY:")
    print(f"🎨 Team preference: {global_team_preference or 'Auto'}")
    print(f"⛽ Fuel strategy: {global_fuel_strategy} (min threshold: {global_min_fuel_threshold})")
    print(f"👥 Active accounts: {len(active_accounts)}")
    
    confirm = input("\nStart continuous voting? (y/n): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("❌ Continuous voting cancelled!")
        return
    
    vote_cycle = 0
    is_first_vote_cycle = True  # Flag untuk cycle pertama (no delay)
    
    try:
        while True:
            vote_cycle += 1
            print(f"\n🔄 VOTE CYCLE #{vote_cycle}")
            print("=" * 50)
            
            # Get match timing dari salah satu account
            if not active_accounts:
                print("❌ No active accounts remaining!")
                break
            
            # Setup bot dari account pertama untuk get timing info
            temp_bot = FarcasterAutoVote(active_accounts[0]['token'], 1, 10, None)
            
            # Get current match timing
            match_details = temp_bot.get_match_details()
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
                
                print(f"\n🚀 Voting window opened! Starting multi-account voting...")
                
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
            
            # Vote semua account dengan random delay per account
            print(f"\n{colored_text('╔' + '═' * 68 + '╗', Colors.GREEN)}")
            print(f"{colored_text('║', Colors.GREEN)} {colored_text(f'🗳️ Starting vote cycle #{vote_cycle} for all accounts...', Colors.BOLD + Colors.WHITE):>60} {colored_text('║', Colors.GREEN)}")
            print(f"{colored_text('╚' + '═' * 68 + '╝', Colors.GREEN)}")
            successful_votes = 0
            failed_votes = 0
            
            # Generate random delays untuk setiap account dengan custom config
            account_delays = {}
            
            if is_first_vote_cycle:
                # Cycle pertama - TANPA delay untuk semua account
                print(f"🚀 First vote cycle - NO DELAY for all accounts (immediate voting)")
                for acc in active_accounts:
                    account_delays[acc['index']] = 0
                is_first_vote_cycle = False
            else:
                # Continuous cycles - DENGAN delay random
                print(f"🎲 Continuous cycle - Random delays applied:")
                for i, acc in enumerate(active_accounts):
                    # Set unique seed per account per cycle untuk true randomness
                    account_seed = int(time.time() * 1000) + vote_cycle * 1000 + acc['index'] * 100 + i
                    random.seed(account_seed)
                    delay = random.randint(min_delay, max_delay)  # Gunakan custom config
                    account_delays[acc['index']] = delay
                    print(f"🎲 Account {acc['index']} random delay: {format_duration(delay)}")
            
            for acc in active_accounts[:]:  # Copy list untuk avoid modification during iteration
                print(f"\n{colored_text('┌─ Account Status ─' + '─' * 49 + '┐', Colors.CYAN)}")
                acc_index = acc.get('index', 'Unknown')
                acc_fid = acc.get('fid', 'Unknown')
                print(f"{colored_text('│', Colors.CYAN)} {colored_text(f'👤 Account {acc_index}', Colors.BOLD + Colors.WHITE):<20} {colored_text(f'🆔 FID: {acc_fid}', Colors.YELLOW):<25} {colored_text('│', Colors.CYAN)}")
                print(f"{colored_text('└' + '─' * 68 + '┘', Colors.CYAN)}")
                try:
                    # Update fuel info
                    temp_bot = FarcasterAutoVote(acc['token'], 1, 10, None)
                    current_fuel = temp_bot.get_user_fuel_info()
                    
                    if current_fuel <= 0:
                        print(f"{colored_text(f'❌ Account {acc_index}: No fuel remaining, removing from active list', Colors.RED)}")
                        active_accounts.remove(acc)
                        continue
                    
                    acc['fuel'] = current_fuel
                    print(f"{colored_text(f'⛽ Current fuel: {current_fuel}', Colors.GREEN)}")
                    
                    # Determine fuel to use based on global strategy
                    if fuel_strategy == "conservative":
                        fuel_to_use = min_fuel_threshold
                    elif fuel_strategy == "max":
                        fuel_to_use = current_fuel
                    elif fuel_strategy == "custom":
                        fuel_to_use = min(min_fuel_threshold, current_fuel)
                    else:
                        fuel_to_use = current_fuel  # Default to max
                    
                    print(f"{colored_text(f'🎯 Using {fuel_to_use} fuel for this vote (strategy: {fuel_strategy})', Colors.YELLOW)}")
                    
                    # TAMBAHAN: Random delay sebelum vote (hanya jika ada delay)
                    delay_time = account_delays[acc_index]
                    if delay_time > 0:
                        print(f"{colored_text(f'🎲 Random delay: {format_duration(delay_time)} before voting...', Colors.MAGENTA)}")
                        
                        # Countdown untuk delay
                        remaining_delay = delay_time
                        while remaining_delay > 0:
                            print(f"{colored_text(f'⏳ Account {acc_index} voting in {format_duration(remaining_delay)}', Colors.CYAN)}", end='\r')
                            sleep_time = min(5, remaining_delay)  # Update setiap 5 detik
                            time.sleep(sleep_time)
                            remaining_delay -= sleep_time
                        
                        print(f"\n{colored_text(f'🎯 Account {acc_index}: Random delay finished, voting now!', Colors.GREEN)}")
                    else:
                        print(f"{colored_text(f'🎯 Account {acc_index}: No delay - voting immediately!', Colors.GREEN)}")
                    
                    # Attempt vote with global team preference
                    bot_team_pref = None if team_preference == "auto" else team_preference
                    bot = FarcasterAutoVote(acc['token'], fuel_to_use, current_fuel, bot_team_pref)
                    success = bot.run_auto_vote()
                    
                    if success:
                        print(f"{colored_text(f'✅ Account {acc_index}: Vote successful!', Colors.GREEN)}")
                        successful_votes += 1
                        acc['fuel'] -= fuel_to_use  # Update fuel count
                    else:
                        print(f"{colored_text(f'❌ Account {acc_index}: Vote failed!', Colors.RED)}")
                        failed_votes += 1
                        
                except Exception as e:
                    print(f"{colored_text(f'❌ Account {acc_index}: Error - {e}', Colors.RED)}")
                    failed_votes += 1
                
                # Small delay between accounts
                time.sleep(2)
            
            # Summary untuk cycle ini
            print(f"\n{colored_text('╔' + '═' * 68 + '╗', Colors.MAGENTA)}")
            print(f"{colored_text('║', Colors.MAGENTA)} {colored_text(f'📊 CYCLE #{vote_cycle} SUMMARY', Colors.BOLD + Colors.WHITE):>50} {colored_text('║', Colors.MAGENTA)}")
            print(f"{colored_text('║', Colors.MAGENTA)} {colored_text(f'✅ Successful votes: {successful_votes}', Colors.GREEN):<35} {colored_text('║', Colors.MAGENTA)}")
            print(f"{colored_text('║', Colors.MAGENTA)} {colored_text(f'❌ Failed votes: {failed_votes}', Colors.RED):<35} {colored_text('║', Colors.MAGENTA)}")
            print(f"{colored_text('║', Colors.MAGENTA)} {colored_text(f'⛽ Active accounts remaining: {len(active_accounts)}', Colors.CYAN):<35} {colored_text('║', Colors.MAGENTA)}")
            print(f"{colored_text('╚' + '═' * 68 + '╝', Colors.MAGENTA)}")
            
            if successful_votes > 0:
                # Show timing info dan get status
                status, remaining_time = show_match_timing_info(current_match)
                
                if status == 'open' and remaining_time > 0:
                    print(f"\n{colored_text('┌─ Waiting Status ─' + '─' * 48 + '┐', Colors.YELLOW)}")
                    print(f"{colored_text('│', Colors.YELLOW)} {colored_text(f'⏳ Waiting {format_duration(remaining_time)} until voting ends...', Colors.WHITE):<60} {colored_text('│', Colors.YELLOW)}")
                    print(f"{colored_text('│', Colors.YELLOW)} {colored_text('💤 All accounts voted, sleeping until next voting window...', Colors.CYAN):<60} {colored_text('│', Colors.YELLOW)}")
                    print(f"{colored_text('└' + '─' * 68 + '┘', Colors.YELLOW)}")
                    
                    # Sleep dengan progress indicator sampai voting ends
                    voting_end_str = current_match.get('votingEndTime') or current_match.get('endTime')
                    if voting_end_str:
                        voting_end = parse_iso_time(voting_end_str)
                        
                        while datetime.datetime.now(pytz.UTC) < voting_end:
                            remaining = (voting_end - datetime.datetime.now(pytz.UTC)).total_seconds()
                            if remaining <= 0:
                                break
                            print(f"{colored_text(f'⏰ Voting ends in {format_duration(remaining)}', Colors.YELLOW)}", end='\r')
                            time.sleep(min(30, remaining))
                    
                    print(f"\n🔄 Voting window ended, checking for next match...")
                    
                # Wait for next match dengan deteksi timing yang akurat
                print(f"\n{colored_text('🔍 NEXT MATCH DETECTION', Colors.BOLD + Colors.BLUE)}")
                print(f"{colored_text('⚡ Starting intelligent match detection...', Colors.CYAN)}")
                
                # Setup bot untuk deteksi match berikutnya
                temp_bot = FarcasterAutoVote(active_accounts[0]['token'], 1, 10, None)
                
                # Wait dan deteksi match berikutnya
                found_new_match, new_match_data = wait_for_next_match(temp_bot, max_wait_minutes=30)
                
                if found_new_match and new_match_data:
                    print(f"{colored_text('🎉 New match detected! Continuing with next cycle...', Colors.GREEN)}")
                    # Update current_match untuk cycle berikutnya
                    current_match = new_match_data
                else:
                    print(f"{colored_text('⚠️ No new match found, waiting 5 minutes before retry...', Colors.YELLOW)}")
                    time.sleep(300)
                    
            else:
                print("💡 All votes failed, checking again in 2 minutes...")
                time.sleep(120)
                    
            # Small delay before next cycle
            print("\n" + "="*60)
            time.sleep(5)
                
    except KeyboardInterrupt:
        print(f"\n\n⛔ Continuous multi-account auto vote stopped by user")
        print(f"📊 Total vote cycles: {vote_cycle}")
        print("👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Unexpected error in continuous vote: {e}")
        print(f"📊 Total vote cycles: {vote_cycle}")

def signal_handler(sig, frame):
    """Handle Ctrl+C signal untuk force exit"""
    print(f"\n\n{colored_text('⛔ CTRL+C DETECTED! FORCE STOPPING ALL PROCESSES...', Colors.BOLD + Colors.RED)}")
    print(f"{colored_text('👋 Exiting immediately...', Colors.YELLOW)}")
    
    # Force terminate semua threads dan processes
    try:
        import threading
        # Set all threads as daemon so they die with main process
        for thread in threading.enumerate():
            if thread != threading.current_thread():
                thread.daemon = True
    except:
        pass
    
    # Force exit
    os._exit(0)

def main():
    """Main function with multi account support"""
    # Setup signal handler untuk Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
def main():
    """Main function with multi account support"""
    # Clear screen for better presentation
    os.system('cls' if os.name == 'nt' else 'clear')
    
    # Animated header
    header_lines = [
        "╔══════════════════════════════════════════════════════════════════╗",
        "║                    🚀 FARCASTER AUTO VOTE SCRIPT                ║",
        "║                         MULTI ACCOUNT EDITION                   ║",
        "╠══════════════════════════════════════════════════════════════════╣",
        "║  💫 Advanced Automated Voting System v2.0                      ║",
        "║  🔥 Powered by AI & Multi-Threading Technology                  ║",
        "║  ⚡ Real-time Fuel Management & Auto-Claim                     ║",
        "╚══════════════════════════════════════════════════════════════════╝"
    ]
    
    for line in header_lines:
        print(colored_text(line, Colors.BOLD + Colors.CYAN))
        time.sleep(0.1)
    
    print(f"\n{colored_text('🔍 Initializing system...', Colors.YELLOW)}")
    
    # Load all tokens dari account.txt
    print(f"{colored_text('� Loading authorization tokens...', Colors.BLUE)}")
    auth_tokens = load_authorization_token()
    if not auth_tokens:
        print(colored_text("❌ Error: Could not load any authorization tokens!", Colors.RED))
        return
    
    print(f"{colored_text(f'✅ Successfully loaded {len(auth_tokens)} token(s)', Colors.GREEN)}")
    
    # Detect fuel untuk semua account
    print(f"\n{colored_text(f'🔍 Scanning fuel balance for {len(auth_tokens)} account(s)...', Colors.MAGENTA)}")
    print(f"{colored_text('⏳ Please wait while detecting account information...', Colors.YELLOW)}")
    account_info = []
    
    for i, token in enumerate(auth_tokens, 1):
        print(f"{colored_text(f'🔄 Scanning Account {i}/{len(auth_tokens)}...', Colors.CYAN)}", end=' ')
        try:
            temp_bot = FarcasterAutoVote(token, 1, 10, None)
            fuel = temp_bot.get_user_fuel_info()
            username = temp_bot.user_id  # FID yang terdeteksi
            
            account_info.append({
                'index': i,
                'token': token,
                'fid': username,
                'fuel': fuel
            })
            
            if fuel > 0:
                print(f"{colored_text('✅ FOUND FUEL', Colors.GREEN)} - {colored_text(f'FID: {username}', Colors.WHITE)} {colored_text('|', Colors.CYAN)} {colored_text(f'Fuel: {fuel}', Colors.YELLOW)}")
            else:
                print(f"{colored_text('⛽ NO FUEL', Colors.RED)} - {colored_text(f'FID: {username}', Colors.WHITE)}")
        except Exception as e:
            print(f"{colored_text('❌', Colors.RED)} {colored_text(f'Error: {str(e)[:30]}...', Colors.RED)}")
            account_info.append({
                'index': i,
                'token': token,
                'fid': 'Unknown',
                'fuel': 0
            })
    
    if not account_info:
        print(colored_text("\n❌ No valid accounts found!", Colors.RED))
        return
    
    # Account summary with colors
    total_fuel = sum(acc['fuel'] for acc in account_info)
    active_accounts = len([acc for acc in account_info if acc['fuel'] > 0])
    
    print(f"\n{colored_text('═' * 70, Colors.MAGENTA)}")
    print(f"{colored_text('📊 ACCOUNT SUMMARY', Colors.BOLD + Colors.MAGENTA)}")
    print(f"{colored_text('═' * 70, Colors.MAGENTA)}")
    print(f"{colored_text('💰 Total Fuel Available:', Colors.YELLOW)} {colored_text(str(total_fuel), Colors.GREEN if total_fuel > 0 else Colors.RED)}")
    print(f"{colored_text('🟢 Active Accounts:', Colors.YELLOW)} {colored_text(f'{active_accounts}/{len(account_info)}', Colors.GREEN if active_accounts > 0 else Colors.RED)}")
    print(f"{colored_text('═' * 70, Colors.MAGENTA)}")
    
    # Main menu options with colors
    print(f"\n{colored_text('🎛️  CONTROL PANEL - SELECT ACTION', Colors.BOLD + Colors.CYAN)}")
    menu_lines = [
        "┌─────────────────────────────────────────────────────────────────┐",
        "│  1. 🚀 Auto Vote All Accounts (Continuous Loop)                │",
        "│  2. ⛽ Check Fuel Status All                                   │",
        "│  3. 🚪 Exit                                                    │",
        "└─────────────────────────────────────────────────────────────────┘"
    ]
    
    for line in menu_lines:
        print(colored_text(line, Colors.BLUE))
    
    action_choice = input(f"\n{colored_text('💫 Choose your action (1/2/3):', Colors.BOLD + Colors.YELLOW)} ").strip()
    
    if action_choice == "2":
        # Check fuel status semua account with colors
        print(f"\n{colored_text('═' * 70, Colors.CYAN)}")
        print(f"{colored_text('⛽ DETAILED FUEL STATUS REPORT', Colors.BOLD + Colors.CYAN)}")
        print(f"{colored_text('═' * 70, Colors.CYAN)}")
        
        for acc in account_info:
            if acc['fuel'] > 0:
                status_color = Colors.GREEN
                fuel_color = Colors.GREEN
                status_emoji = "🟢"
            else:
                status_color = Colors.RED
                fuel_color = Colors.RED
                status_emoji = "🔴"
            
            status_line = f"{status_emoji} Account {acc['index']:2d} │ FID: {acc['fid']:8s} │ Fuel: {acc['fuel']:3d}"
            print(f"{colored_text(status_emoji, status_color)} {colored_text(f'Account {acc['index']:2d}', Colors.WHITE)} {colored_text('│', Colors.CYAN)} {colored_text(f'FID: {acc['fid']:8s}', Colors.YELLOW)} {colored_text('│', Colors.CYAN)} {colored_text(f'Fuel: {acc['fuel']:3d}', fuel_color)}")
        
        print(f"{colored_text('═' * 70, Colors.CYAN)}")
        return
        
    elif action_choice == "3":
        print(f"\n{colored_text('═' * 70, Colors.MAGENTA)}")
        print(f"{colored_text('👋 Thank you for using Farcaster Auto Vote!', Colors.BOLD + Colors.CYAN)}")
        print(f"{colored_text('💫 See you next time!', Colors.YELLOW)}")
        print(f"{colored_text('═' * 70, Colors.MAGENTA)}")
        return
        
    elif action_choice != "1":
        print(f"{colored_text('❌ Invalid choice! Please select 1, 2, or 3.', Colors.RED)}")
        return
    
    # Option 1: Auto Vote All Accounts (Continuous Loop)
    
    # TEAM PREFERENCE CONFIGURATION
    print(f"\n{colored_text('═' * 70, Colors.MAGENTA)}")
    print(f"{colored_text('🎯 TEAM PREFERENCE CONFIGURATION', Colors.BOLD + Colors.MAGENTA)}")
    print(f"{colored_text('═' * 70, Colors.MAGENTA)}")
    
    team_menu_lines = [
        "┌─────────────────────────────────────────────────────────────────┐",
        "│  1. 🔵 Blue Team (Always vote for Blue Team)                   │",
        "│  2. 🔴 Red Team (Always vote for Red Team)                     │", 
        "│  3. 🎲 Auto (Random team selection for each vote)              │",
        "└─────────────────────────────────────────────────────────────────┘"
    ]
    
    for line in team_menu_lines:
        print(colored_text(line, Colors.BLUE))
    
    team_choice = input(f"\n{colored_text('🎯 Select team preference (1/2/3):', Colors.BOLD + Colors.YELLOW)} ").strip()
    
    if team_choice == "1":
        global_team_preference = "blue"
        print(f"{colored_text('✅ Team preference set to: Blue Team', Colors.BLUE)}")
    elif team_choice == "2":
        global_team_preference = "red"
        print(f"{colored_text('✅ Team preference set to: Red Team', Colors.RED)}")
    else:
        global_team_preference = "auto"
        print(f"{colored_text('✅ Team preference set to: Auto (Random)', Colors.YELLOW)}")
    
    # FUEL STRATEGY CONFIGURATION
    print(f"\n{colored_text('═' * 70, Colors.MAGENTA)}")
    print(f"{colored_text('⛽ FUEL STRATEGY CONFIGURATION', Colors.BOLD + Colors.MAGENTA)}")
    print(f"{colored_text('═' * 70, Colors.MAGENTA)}")
    
    fuel_menu_lines = [
        "┌─────────────────────────────────────────────────────────────────┐",
        "│  1. 🛡️  Conservative (Use only when fuel > 3)                  │",
        "│  2. 🚀 Max Available (Use all available fuel)                  │",
        "│  3. ⚙️  Custom (Set minimum fuel threshold)                    │",
        "└─────────────────────────────────────────────────────────────────┘"
    ]
    
    for line in fuel_menu_lines:
        print(colored_text(line, Colors.BLUE))
    
    fuel_choice = input(f"\n{colored_text('⛽ Select fuel strategy (1/2/3):', Colors.BOLD + Colors.YELLOW)} ").strip()
    
    if fuel_choice == "1":
        global_fuel_strategy = "conservative"
        global_min_fuel_threshold = 3
        print(f"{colored_text('✅ Fuel strategy set to: Conservative (min fuel: 3)', Colors.GREEN)}")
    elif fuel_choice == "3":
        global_fuel_strategy = "custom"
        try:
            global_min_fuel_threshold = int(input("Enter minimum fuel threshold: ") or "1")
            if global_min_fuel_threshold < 1:
                global_min_fuel_threshold = 1
        except ValueError:
            global_min_fuel_threshold = 1
        print(f"{colored_text(f'✅ Fuel strategy set to: Custom (min fuel: {global_min_fuel_threshold})', Colors.GREEN)}")
    else:
        global_fuel_strategy = "max"
        global_min_fuel_threshold = 1
        print(f"{colored_text('✅ Fuel strategy set to: Max Available (min fuel: 1)', Colors.GREEN)}")
    
    # Ask for threading preference
    print(f"\n{colored_text('═' * 70, Colors.MAGENTA)}")
    print(f"{colored_text('🧵 EXECUTION MODE CONFIGURATION', Colors.BOLD + Colors.MAGENTA)}")
    print(f"{colored_text('═' * 70, Colors.MAGENTA)}")
    print("🔄 Sequential: Accounts akan vote satu per satu (lebih stabil)")
    print("🧵 Threaded: Semua accounts vote bersamaan (lebih cepat)")
    
    use_threading_input = input(f"\n{colored_text('🧵 Use multi-threading? (y/n):', Colors.BOLD + Colors.YELLOW)} ").strip().lower()
    use_threading = use_threading_input in ['y', 'yes', '1', 'true']
    
    # Custom delay configuration
    print(f"\n🎲 CUSTOM RANDOM DELAY CONFIGURATION:")
    print("Configure random delay interval setelah voting starts untuk anti-bot detection")
    
    if use_threading:
        print(f"\n⚙️ THREADING MODE DELAY:")
        print("1. Quick (30 seconds - 2 minutes)")
        print("2. Normal (30 seconds - 5 minutes)  [Default]")
        print("3. Safe (1 minute - 8 minutes)")
        print("4. Conservative (2 minutes - 10 minutes)")
        print("5. Custom Range")
        
        delay_choice = input("\nPilih delay range (1/2/3/4/5): ").strip()
        
        if delay_choice == "1":
            min_delay, max_delay = 30, 120  # 30s - 2m
        elif delay_choice == "3":
            min_delay, max_delay = 60, 480  # 1m - 8m
        elif delay_choice == "4":
            min_delay, max_delay = 120, 600  # 2m - 10m
        elif delay_choice == "5":
            try:
                min_delay = int(input("Minimum delay (seconds): ") or "30")
                max_delay = int(input("Maximum delay (seconds): ") or "300")
                if min_delay >= max_delay:
                    print("⚠️ Invalid range, using default")
                    min_delay, max_delay = 30, 300
            except ValueError:
                print("⚠️ Invalid input, using default")
                min_delay, max_delay = 30, 300
        else:
            min_delay, max_delay = 30, 300  # Default: 30s - 5m
            
    else:
        print(f"\n⚙️ SEQUENTIAL MODE DELAY:")
        print("1. Quick (5 seconds - 1 minute)")
        print("2. Normal (5 seconds - 3 minutes)  [Default]")
        print("3. Safe (10 seconds - 5 minutes)")
        print("4. Conservative (30 seconds - 8 minutes)")
        print("5. Custom Range")
        
        delay_choice = input("\nPilih delay range (1/2/3/4/5): ").strip()
        
        if delay_choice == "1":
            min_delay, max_delay = 5, 60    # 5s - 1m
        elif delay_choice == "3":
            min_delay, max_delay = 10, 300  # 10s - 5m
        elif delay_choice == "4":
            min_delay, max_delay = 30, 480  # 30s - 8m
        elif delay_choice == "5":
            try:
                min_delay = int(input("Minimum delay (seconds): ") or "5")
                max_delay = int(input("Maximum delay (seconds): ") or "180")
                if min_delay >= max_delay:
                    print("⚠️ Invalid range, using default")
                    min_delay, max_delay = 5, 180
            except ValueError:
                print("⚠️ Invalid input, using default")
                min_delay, max_delay = 5, 180
        else:
            min_delay, max_delay = 5, 180   # Default: 5s - 3m
    
    print(f"\n✅ DELAY CONFIGURATION:")
    print(f"🎲 Random delay range: {format_duration(min_delay)} - {format_duration(max_delay)}")
    print(f"🎯 Mode: {'Threading' if use_threading else 'Sequential'}")
    
    # Pass delay configuration to voting functions
    delay_config = {'min_delay': min_delay, 'max_delay': max_delay}
    
    # Show final configuration summary
    print(f"\n{colored_text('═' * 70, Colors.MAGENTA)}")
    print(f"{colored_text('📋 FINAL CONFIGURATION SUMMARY', Colors.BOLD + Colors.MAGENTA)}")
    print(f"{colored_text('═' * 70, Colors.MAGENTA)}")
    print(f"{colored_text('🎯 Team Preference:', Colors.YELLOW)} {colored_text(global_team_preference.title(), Colors.CYAN)}")
    print(f"{colored_text('⛽ Fuel Strategy:', Colors.YELLOW)} {colored_text(global_fuel_strategy.title(), Colors.CYAN)} (min: {global_min_fuel_threshold})")
    print(f"{colored_text('🎲 Delay Range:', Colors.YELLOW)} {colored_text(f'{format_duration(min_delay)} - {format_duration(max_delay)}', Colors.CYAN)}")
    print(f"{colored_text('🧵 Execution Mode:', Colors.YELLOW)} {colored_text('Threading' if use_threading else 'Sequential', Colors.CYAN)}")
    print(f"{colored_text('═' * 70, Colors.MAGENTA)}")
    
    if use_threading:
        print(f"{colored_text('🧵 Using threaded execution mode...', Colors.GREEN)}")
        print(f"{colored_text('🎯 Each account will have independent continuous cycles...', Colors.GREEN)}")
        
        # Filter active accounts untuk threading
        active_accounts = [acc for acc in account_info if acc['fuel'] >= global_min_fuel_threshold]
        if not active_accounts:
            print(f"{colored_text('❌ No accounts meet the fuel threshold!', Colors.RED)}")
            return
            
        threaded_continuous_multi_account_vote(
            active_accounts, 
            delay_config=delay_config,
            team_preference=global_team_preference,
            fuel_strategy=global_fuel_strategy,
            min_fuel_threshold=global_min_fuel_threshold
        )
    else:
        print(f"{colored_text('🔄 Using sequential execution mode...', Colors.GREEN)}")
        continuous_multi_account_vote(
            account_info, 
            delay_config=delay_config,
            team_preference=global_team_preference,
            fuel_strategy=global_fuel_strategy,
            min_fuel_threshold=global_min_fuel_threshold
        )

if __name__ == "__main__":
    main()
