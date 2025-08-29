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
import pytz
import os
import uuid
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import unquote, quote

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
    """Tampilkan info timing match"""
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
            elif voting_start <= now_utc <= voting_end:
                remaining_time = (voting_end - now_utc).total_seconds()
                print(f"✅ Voting is OPEN! Ends in: {format_duration(remaining_time)}")
            else:
                print("⌛ Voting window has CLOSED")
    except Exception as e:
        print(f"⚠️ Could not parse timing info: {e}")

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
                    # Cek apakah fuel amount tidak melebihi max fuel
                    if self.fuel_amount > self.max_fuel:
                        print(f"⚠️  Fuel amount ({self.fuel_amount}) melebihi max fuel ({self.max_fuel})")
                        fuel_points = self.max_fuel
                    else:
                        fuel_points = self.fuel_amount
                else:
                    fuel_points = 1  # Default 1 fuel
            
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

def run_account_continuous_thread(account_info, thread_id):
    """Run continuous voting untuk satu akun dalam thread terpisah"""
    try:
        account = account_info[thread_id]
        fid = account['fid']
        token = account['token']
        fuel = account['fuel']
        
        print(f"\n🧵 [Thread-{thread_id+1}] Starting continuous voting for Account {account['index']} (FID: {fid})")
        
        # Initialize bot untuk account ini
        bot = FarcasterAutoVote(token, 1, 10, None)
        
        cycle_count = 0
        
        while True:  # Continuous loop untuk account ini
            try:
                cycle_count += 1
                print(f"\n{colored_text('╔' + '═' * 68 + '╗', Colors.MAGENTA)}")
                thread_text = f"🔄 [Thread-{thread_id+1}] CYCLE #{cycle_count} - Account {account['index']} (FID: {fid})"
                print(f"{colored_text('║', Colors.MAGENTA)} {colored_text(thread_text, Colors.BOLD + Colors.WHITE):>60} {colored_text('║', Colors.MAGENTA)}")
                print(f"{colored_text('╚' + '═' * 68 + '╝', Colors.MAGENTA)}")
                
                current_fuel = bot.get_user_fuel_info()
                print(f"{colored_text(f'⛽ [Thread-{thread_id+1}] Current fuel: {current_fuel}', Colors.GREEN)}")
                
                # Get match details
                match_details = bot.get_match_details()
                if not match_details or 'data' not in match_details or not match_details['data']['matchData']:
                    print(f"{colored_text(f'❌ [Thread-{thread_id+1}] No active match found, waiting 2 minutes...', Colors.RED)}")
                    time.sleep(120)
                    continue
                
                current_match = match_details['data']['matchData'][0]
                
                # Check if voting is open
                timing_info = get_voting_timing(current_match)
                if timing_info['status'] == 'open':
                    print(f"{colored_text(f'✅ [Thread-{thread_id+1}] Voting is open, attempting to vote...', Colors.GREEN)}")
                    
                    # Try to vote
                    success = bot.submit_prediction()
                    
                    if success:
                        print(f"{colored_text(f'🎉 [Thread-{thread_id+1}] Vote submitted successfully! 🎯', Colors.BOLD + Colors.GREEN)}")
                        
                        # Wait until voting ends
                        if timing_info.get('remaining_vote_time'):
                            wait_time = timing_info['remaining_vote_time']
                            print(f"{colored_text(f'⏳ [Thread-{thread_id+1}] Waiting {format_duration(wait_time)} until voting ends...', Colors.YELLOW)}")
                            
                            # Sleep dengan progress indicator
                            sleep_interval = min(60, wait_time / 10)
                            slept = 0
                            while slept < wait_time:
                                remaining = wait_time - slept
                                print(f"{colored_text(f'⏰ [Thread-{thread_id+1}] Next check in {format_duration(remaining)}', Colors.CYAN)}", end='\r')
                                sleep_time = min(sleep_interval, remaining)
                                time.sleep(sleep_time)
                                slept += sleep_time
                                if remaining <= 0:
                                    break
                            
                            print(f"\n{colored_text(f'🔄 [Thread-{thread_id+1}] Voting ended, looking for next match...', Colors.BLUE)}")
                        else:
                            print(f"{colored_text(f'⏳ [Thread-{thread_id+1}] Waiting 5 minutes before next check...', Colors.YELLOW)}")
                            time.sleep(300)
                    else:
                        print(f"{colored_text(f'❌ [Thread-{thread_id+1}] Vote failed, waiting 2 minutes...', Colors.RED)}")
                        time.sleep(120)
                        
                elif timing_info['status'] == 'waiting':
                    wait_time = timing_info.get('time_until_start', 300)
                    print(f"{colored_text(f'⏳ [Thread-{thread_id+1}] Voting not started yet, waiting {format_duration(wait_time)}...', Colors.YELLOW)}")
                    time.sleep(min(wait_time, 300))  # Max 5 minutes wait
                    
                elif timing_info['status'] == 'ended':
                    print(f"{colored_text(f'⏳ [Thread-{thread_id+1}] Voting ended, waiting for next match...', Colors.BLUE)}")
                    time.sleep(300)  # Wait 5 minutes
                else:
                    print(f"{colored_text(f'⚠️  [Thread-{thread_id+1}] Unknown timing status, waiting 2 minutes...', Colors.YELLOW)}")
                    time.sleep(120)
                    
                # Small delay before next cycle
                time.sleep(5)
                
            except Exception as e:
                print(f"{colored_text(f'❌ [Thread-{thread_id+1}] Error in cycle: {e}', Colors.RED)}")
                time.sleep(60)  # Wait 1 minute on error
                
    except KeyboardInterrupt:
        account_index = account.get('index', 'Unknown')
        print(f"\n{colored_text(f'⛔ [Thread-{thread_id+1}] Account {account_index} thread stopped by user', Colors.BOLD + Colors.RED)}")
    except Exception as e:
        print(f"\n{colored_text(f'❌ [Thread-{thread_id+1}] Thread error: {e}', Colors.RED)}")

def threaded_continuous_multi_account_vote(active_accounts):
    """Run multi-account voting dengan threading - setiap akun punya continuous loop sendiri"""
    import threading
    
    print(f"\n🧵 Starting threaded continuous voting for {len(active_accounts)} accounts...")
    print("⚠️  Each account will run in its own continuous loop")
    print("⚠️  Press Ctrl+C to stop all threads")
    
    threads = []
    
    try:
        # Create dan start thread untuk setiap account
        for i, account in enumerate(active_accounts):
            thread = threading.Thread(
                target=run_account_continuous_thread,
                args=(active_accounts, i),
                daemon=True,
                name=f"Account-{account['index']}-Thread"
            )
            threads.append(thread)
            thread.start()
            print(f"🧵 Started thread for Account {account['index']} (FID: {account['fid']})")
            time.sleep(2)  # Delay antar thread start
        
        print(f"\n✅ All {len(threads)} threads started successfully!")
        print("🔄 Threads are running continuously...")
        print("⛔ Press Ctrl+C to stop all threads")
        
        # Wait for all threads
        for thread in threads:
            thread.join()
            
    except KeyboardInterrupt:
        print(f"\n\n⛔ Threaded multi-account voting stopped by user")
        print("👋 All threads will be terminated...")
    except Exception as e:
        print(f"\n❌ Threading error: {e}")

def threaded_multi_account_vote(account_info_list, use_threading=False):
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
    
    # Get team preference
    print("\n🎯 PILIH PREFERENSI TIM:")
    print("1. Blue Team (Biru/Kanan)")
    print("2. Red Team (Merah/Kiri)")  
    print("3. Auto (Based on winning probability)")
    
    team_choice = input("Pilih tim (1/2/3): ").strip()
    team_preference = None
    if team_choice == "1":
        team_preference = "blue"
    elif team_choice == "2":
        team_preference = "red"
    elif team_choice == "3":
        team_preference = None
    else:
        print("⚠️  Invalid choice, using Auto")
        team_preference = None
    
    # Get fuel strategy
    print(f"\n⛽ PILIH STRATEGI FUEL:")
    print("1. Conservative (1 fuel)")
    print("2. Max Available Fuel")
    print("3. Custom Amount")
    
    fuel_choice = input("Pilih strategi fuel (1/2/3): ").strip()
    fuel_strategy = "max"
    custom_fuel = None
    
    if fuel_choice == "1":
        fuel_strategy = "conservative"
        custom_fuel = 1
    elif fuel_choice == "2":
        fuel_strategy = "max"
    elif fuel_choice == "3":
        fuel_strategy = "custom"
        try:
            custom_fuel = int(input("Masukkan jumlah fuel (1-10): "))
            if custom_fuel < 1 or custom_fuel > 10:
                print("⚠️  Invalid fuel amount, using 1")
                custom_fuel = 1
        except ValueError:
            print("⚠️  Invalid input, using 1 fuel")
            custom_fuel = 1
    else:
        print("⚠️  Invalid choice, using Max Fuel")
    
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
                print(f"{colored_text('│', Colors.MAGENTA)} {colored_text(f'🧵 Using threaded execution for {len(account_info_list)} accounts...', Colors.WHITE):<60} {colored_text('│', Colors.MAGENTA)}")
                print(f"{colored_text('└' + '─' * 68 + '┘', Colors.MAGENTA)}")
                results_queue = queue.Queue()
                
                with ThreadPoolExecutor(max_workers=len(account_info_list)) as executor:
                    # Submit all tasks
                    future_to_account = {
                        executor.submit(process_single_account_vote, acc_info, team_preference, fuel_strategy, custom_fuel, results_queue): acc_info
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
                    result = process_single_account_vote(acc_info, team_preference, fuel_strategy, custom_fuel, results_queue)
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
                # Get timing info from first successful account
                try:
                    first_successful_token = next(acc['token'] for acc in account_info_list 
                                                if any(r['account_index'] == acc['index'] and r['success'] for r in all_results))
                    temp_bot = FarcasterAutoVote(first_successful_token, 1, 10, None)
                    match_details = temp_bot.get_match_details()
                    
                    if match_details and 'data' in match_details and match_details['data']['matchData']:
                        current_match = match_details['data']['matchData'][0]
                        
                        # Calculate wait time until voting ends - try multiple field names
                        voting_end_str = current_match.get('votingEndTime') or current_match.get('endTime') or current_match.get('votingEnd')
                        if voting_end_str:
                            voting_end = parse_iso_time(voting_end_str)
                            now_utc = datetime.datetime.now(pytz.UTC)
                            
                            if now_utc < voting_end:
                                wait_until_end = (voting_end - now_utc).total_seconds()
                                print(f"\n⏳ Waiting {format_duration(wait_until_end)} until voting ends...")
                                print("💤 All accounts voted, sleeping until next voting window...")
                                
                                # Sleep dengan progress indicator
                                sleep_interval = min(60, wait_until_end / 10)
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
                            print("⚠️  Could not get voting end time, waiting 5 minutes...")
                            time.sleep(300)
                    else:
                        print("⚠️  Could not get match details, waiting 2 minutes...")
                        time.sleep(120)
                        
                except Exception as e:
                    print(f"⚠️  Error getting timing info: {e}, waiting 2 minutes...")
                    time.sleep(120)
            else:
                print("💡 All votes failed, checking again in 2 minutes...")
                time.sleep(120)
                    
            # Small delay before next cycle
            print("\n" + "="*60)
            time.sleep(5)
                
    except KeyboardInterrupt:
        print(f"\n\n⛔ {'Threaded' if use_threading else 'Sequential'} multi-account auto vote stopped by user")
        print(f"📊 Total vote cycles: {vote_cycle}")
        print("👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Unexpected error in {'threaded' if use_threading else 'sequential'} vote: {e}")
        print(f"📊 Total vote cycles: {vote_cycle}")

def continuous_multi_account_vote(account_info):
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
    
    # Filter account yang punya fuel
    active_accounts = [acc for acc in account_info if acc['fuel'] > 0]
    if not active_accounts:
        print("❌ No accounts with fuel available!")
        return
    
    print(f"⛽ Active accounts with fuel: {len(active_accounts)}")
    for acc in active_accounts:
        print(f"   • Account {acc['index']} (FID: {acc['fid']}): {acc['fuel']} fuel")
    
    # Configuration
    print("\n⚙️  TEAM CONFIGURATION:")
    print("1. Blue (Kanan)")
    print("2. Red (Kiri)")
    print("3. Auto (Random/Best Choice)")
    
    team_choice_num = input("\nPilih team untuk semua account (1/2/3): ").strip()
    if team_choice_num == "1":
        team_preference = "blue"
    elif team_choice_num == "2":
        team_preference = "red"
    else:
        team_preference = None
    
    print(f"\n⛽ FUEL CONFIGURATION:")
    print("1. Use 1 fuel per vote (Conservative)")
    print("2. Use max fuel available per account")
    print("3. Custom fuel amount")
    
    fuel_choice = input("\nPilih strategi fuel (1/2/3): ").strip()
    
    if fuel_choice == "1":
        fuel_strategy = "conservative"
        fuel_amount = 1
    elif fuel_choice == "2":
        fuel_strategy = "max"
        fuel_amount = None  # Will use max available
    else:
        fuel_strategy = "custom"
        try:
            fuel_amount = int(input("Masukkan jumlah fuel per vote: ") or "1")
        except ValueError:
            fuel_amount = 1
    
    print(f"\n✅ CONFIGURATION SUMMARY:")
    print(f"🎨 Team preference: {team_preference or 'Auto'}")
    print(f"⛽ Fuel strategy: {fuel_strategy} ({'1 fuel' if fuel_strategy == 'conservative' else 'max available' if fuel_strategy == 'max' else f'{fuel_amount} fuel'})")
    print(f"👥 Active accounts: {len(active_accounts)}")
    
    confirm = input("\nStart continuous voting? (y/n): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("❌ Continuous voting cancelled!")
        return
    
    vote_cycle = 0
    
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
            
            # Vote semua account
            print(f"\n{colored_text('╔' + '═' * 68 + '╗', Colors.GREEN)}")
            print(f"{colored_text('║', Colors.GREEN)} {colored_text(f'🗳️ Starting vote cycle #{vote_cycle} for all accounts...', Colors.BOLD + Colors.WHITE):>60} {colored_text('║', Colors.GREEN)}")
            print(f"{colored_text('╚' + '═' * 68 + '╝', Colors.GREEN)}")
            successful_votes = 0
            failed_votes = 0
            
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
                    
                    # Determine fuel to use
                    if fuel_strategy == "conservative":
                        fuel_to_use = 1
                    elif fuel_strategy == "max":
                        fuel_to_use = current_fuel
                    else:  # custom
                        fuel_to_use = min(fuel_amount, current_fuel)
                    
                    print(f"{colored_text(f'🎯 Using {fuel_to_use} fuel for this vote', Colors.YELLOW)}")
                    
                    # Attempt vote
                    bot = FarcasterAutoVote(acc['token'], fuel_to_use, current_fuel, team_preference)
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
                # Show timing info
                show_match_timing_info(current_match)
                
                # Calculate wait time until voting ends
                now_utc = datetime.datetime.now(pytz.UTC)
                if now_utc < voting_end:
                    wait_until_end = (voting_end - now_utc).total_seconds()
                    print(f"\n{colored_text('┌─ Waiting Status ─' + '─' * 48 + '┐', Colors.YELLOW)}")
                    print(f"{colored_text('│', Colors.YELLOW)} {colored_text(f'⏳ Waiting {format_duration(wait_until_end)} until voting ends...', Colors.WHITE):<60} {colored_text('│', Colors.YELLOW)}")
                    print(f"{colored_text('│', Colors.YELLOW)} {colored_text('💤 All accounts voted, sleeping until next voting window...', Colors.CYAN):<60} {colored_text('│', Colors.YELLOW)}")
                    print(f"{colored_text('└' + '─' * 68 + '┘', Colors.YELLOW)}")
                    
                    # Sleep dengan progress indicator
                    sleep_interval = min(60, wait_until_end / 10)  # Update setiap menit atau 10% dari waktu
                    slept = 0
                    while slept < wait_until_end:
                        remaining = wait_until_end - slept
                        print(f"{colored_text(f'⏰ Next check in {format_duration(remaining)}', Colors.YELLOW)}", end='\r')
                        sleep_time = min(sleep_interval, remaining)
                        time.sleep(sleep_time)
                        slept += sleep_time
                        if remaining <= 0:
                            break
                    
                    print(f"\n🔄 Voting window ended, looking for next match...")
                else:
                    print("🔄 Voting already ended, looking for next match...")
                    
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
    # Ask for threading preference
    print(f"\n🧵 PILIH MODE EXECUTION:")
    print("Sequential: Accounts akan vote satu per satu (lebih stabil)")
    print("Threaded: Semua accounts vote bersamaan (lebih cepat)")
    
    use_threading_input = input("\nUse multi-threading? (y/n): ").strip().lower()
    use_threading = use_threading_input in ['y', 'yes', '1', 'true']
    
    if use_threading:
        print("🧵 Using threaded execution mode...")
        threaded_multi_account_vote(account_info, use_threading=True)
    else:
        print("🔄 Using sequential execution mode...")
        continuous_multi_account_vote(account_info)

if __name__ == "__main__":
    main()
