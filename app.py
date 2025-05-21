# Import required libraries
from flask import Flask, jsonify, request, render_template, send_from_directory
import requests
import os
import json
import time
import tempfile
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app with proper static folder structure
app = Flask(__name__, static_folder='static', static_url_path='/static')

# API configuration
B365_TOKEN = "219761-iALwqep7Hy1aCl"
B365_API_URL = "http://api.b365api.com/v3/events/inplay"
SPORT_ID = 18  # Sport code for basketball

# Function to get storage directory
def get_storage_dir():
    # Check if we're on Render server
    if 'RENDER' in os.environ:
        # Use temporary directory
        return tempfile.gettempdir()
    else:
        # Use current directory
        return '.'

# Location of history and opportunities files
LINES_HISTORY_FILE = os.path.join(get_storage_dir(), 'lines_history.json')
OPPORTUNITIES_FILE = os.path.join(get_storage_dir(), 'opportunities.json')

# Configuration validation
def validate_configuration():
    issues = []
    
    # Check API URL
    if not B365_API_URL or not B365_API_URL.startswith("http"):
        issues.append(f"Invalid API URL: {B365_API_URL}")
    
    # Check token
    if not B365_TOKEN or len(B365_TOKEN) < 10:
        issues.append(f"Invalid API token: {B365_TOKEN}")
    
    # Check write permissions to history files
    storage_dir = get_storage_dir()
    test_file = os.path.join(storage_dir, "test_write.txt")
    try:
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
    except Exception as e:
        issues.append(f"Write permission issue in directory {storage_dir}: {str(e)}")
    
    if issues:
        for issue in issues:
            logger.error(f"Configuration issue: {issue}")
        return False
    
    logger.info("Configuration validation successful")
    return True

# Run configuration validation
is_config_valid = validate_configuration()

# Function to save game lines history
def save_game_lines(game_id, lines_data):
    try:
        # Check if parent directory exists
        parent_dir = os.path.dirname(LINES_HISTORY_FILE)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
        
        # Load existing history
        history = {}
        if os.path.exists(LINES_HISTORY_FILE):
            try:
                with open(LINES_HISTORY_FILE, 'r') as f:
                    history = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                history = {}
        
        # Save new line data
        if game_id not in history:
            history[game_id] = []
        
        # Check if the data has changed since the last update
        changed = True  # Default: assume change
        
        if history[game_id]:
            last_entry = history[game_id][-1]
            # Compare important values
            changed = (
                last_entry.get('spread') != lines_data.get('spread') or
                last_entry.get('total') != lines_data.get('total') or
                last_entry.get('time_status') != lines_data.get('time_status')
            )
        
        if not changed:
            return False
        
        # Add line data with timestamp
        lines_data['timestamp'] = datetime.now().isoformat()
        history[game_id].append(lines_data)
        
        # Save to file
        with open(LINES_HISTORY_FILE, 'w') as f:
            json.dump(history, f)
        
        return True
    except Exception as e:
        logger.error(f"Error saving line data: {str(e)}")
        # If error, return True to continue processing
        return True

# Function to get game lines history
def get_game_lines_history(game_id):
    try:
        if not os.path.exists(LINES_HISTORY_FILE):
            return []
        
        with open(LINES_HISTORY_FILE, 'r') as f:
            history = json.load(f)
        
        return history.get(game_id, [])
    except (json.JSONDecodeError, FileNotFoundError, Exception) as e:
        logger.error(f"Error reading lines history: {str(e)}")
        return []

# Function to save opportunities
def save_opportunity(game_id, opportunity_data):
    try:
        # Check if parent directory exists
        parent_dir = os.path.dirname(OPPORTUNITIES_FILE)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
        
        # Load existing opportunities
        opportunities = {}
        if os.path.exists(OPPORTUNITIES_FILE):
            try:
                with open(OPPORTUNITIES_FILE, 'r') as f:
                    opportunities = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                opportunities = {}
        
        # Save new opportunity data
        opportunities[game_id] = opportunity_data
        
        # Save to file
        with open(OPPORTUNITIES_FILE, 'w') as f:
            json.dump(opportunities, f)
        
        return True
    except Exception as e:
        logger.error(f"Error saving opportunity data: {str(e)}")
        return False

# Function to get opportunity
def get_opportunity(game_id):
    try:
        if not os.path.exists(OPPORTUNITIES_FILE):
            return None
        
        with open(OPPORTUNITIES_FILE, 'r') as f:
            opportunities = json.load(f)
        
        return opportunities.get(game_id, None)
    except (json.JSONDecodeError, FileNotFoundError, Exception) as e:
        logger.error(f"Error reading opportunity data: {str(e)}")
        return None

# פונקציה חדשה להבאת נתוני אודס (קווי הימור) ממשחק ספציפי
def fetch_odds_data(bet365_id):
    """
    Get detailed odds information for a specific bet365 event
    """
    if not bet365_id:
        logger.warning("Attempted to fetch odds without bet365_id")
        return None
        
    url = f"https://api.b365api.com/v2/event/odds?token={B365_TOKEN}&event_id={bet365_id}"
    
    try:
        response = requests.get(url, timeout=10)
        logger.info(f"Fetched odds for event {bet365_id}: status {response.status_code}")
        
        if response.status_code == 200:
            return response.json()
            
    except Exception as e:
        logger.error(f"Error fetching odds data for event {bet365_id}: {str(e)}")
    
    return None

# Function to extract line data from a game
def extract_lines_from_game(game):
    """
    Extract line data from a game - adapt to B365 data structure
    Returns an object with spread and total data
    """
    lines_data = {
        'spread': None,
        'total': None,
        'time_status': game.get('time_status'),
        'timestamp': datetime.now().isoformat(),
        'quarter': None,
        'time_remaining': None
    }
    
    # Extract quarter and game clock info
    if 'timer' in game:
        timer = game.get('timer', {})
        lines_data['quarter'] = timer.get('q')
        lines_data['time_remaining'] = timer.get('tm')
    
    # קוד חדש לתיקון הליינים: מביא את המידע מ-API מיוחד לליינים
    # קוד זה ייתן עדיפות לנתונים עדכניים מהקריאה הייעודית
    if 'bet365_id' in game:
        bet365_id = game.get('bet365_id')
        odds_data = fetch_odds_data(bet365_id)
        
        if odds_data and 'results' in odds_data:
            # חיפוש שוק ספרד (handicap/spread) - market_id 18_1 לכדורסל
            for market in odds_data['results']:
                if market.get('market_id') == '18_1':  # קוד לשוק ספרד בכדורסל
                    for odd in market.get('odds', []):
                        if 'handicap' in odd:
                            try:
                                lines_data['spread'] = float(odd['handicap'])
                                logger.info(f"Found spread {lines_data['spread']} for game {bet365_id}")
                                break
                            except (ValueError, TypeError):
                                pass
                
                # חיפוש שוק טוטאל (over/under) - market_id 18_2 לכדורסל
                elif market.get('market_id') == '18_2':  # קוד לשוק טוטאל בכדורסל
                    for odd in market.get('odds', []):
                        if 'handicap' in odd and odd.get('name') == 'Over':
                            try:
                                lines_data['total'] = float(odd['handicap'])
                                logger.info(f"Found total {lines_data['total']} for game {bet365_id}")
                                break
                            except (ValueError, TypeError):
                                pass
    
    # המשך הקוד המקורי במידה והקריאה הנוספת לא הצליחה להביא נתונים
    if lines_data['spread'] is None or lines_data['total'] is None:
        logger.info(f"Falling back to original line extraction method for game {game.get('id')}")
        
        # Extract line data directly from odds if available
        if 'odds' in game:
            for market_type, market_data in game['odds'].items():
                # Search for spread market in B365 format
                if market_type in ['handicap', 'handicap_line', 'ah', 'point_spread'] and lines_data['spread'] is None:
                    try:
                        handicap_val = float(market_data)
                        lines_data['spread'] = handicap_val
                    except (ValueError, TypeError):
                        pass
                
                # Search for total market in B365 format
                elif market_type in ['total', 'total_line', 'ou'] and lines_data['total'] is None:
                    try:
                        total_val = float(market_data)
                        lines_data['total'] = total_val
                    except (ValueError, TypeError):
                        pass
        
        # Handle direct selection data based on first image
        # where we see line +18.5 at odds 1.80
        if not lines_data['spread'] and 'extra' in game:
            extra = game.get('extra', {})
            if 'handicap' in extra:
                try:
                    lines_data['spread'] = float(extra['handicap'])
                except (ValueError, TypeError):
                    pass
        
        # Handle direct information from second image
        # where we see lines like -3.5, -15.5, etc.
        if not lines_data['spread'] and 'odds' in game:
            # Try to extract info in a different structure
            for key, value in game['odds'].items():
                if 'ah_home' in key or 'handicap_home' in key:
                    try:
                        lines_data['spread'] = float(value)
                        break
                    except (ValueError, TypeError):
                        pass
        
        # Extract total from second image
        if not lines_data['total'] and 'odds' in game:
            for key, value in game['odds'].items():
                if 'total' in key.lower() and 'over' in key.lower():
                    try:
                        lines_data['total'] = float(value)
                        break
                    except (ValueError, TypeError):
                        pass
        
        # If we still don't have data, try to extract from the fields shown in the image
        if (not lines_data['spread'] or not lines_data['total']) and 'ss' in game:
            try:
                # From image 1 we see current score is 52-38
                scores = game['ss'].split('-')
                home_score = int(scores[0].strip())
                away_score = int(scores[1].strip())
                
                # If we don't have spread, try to calculate based on current score
                if not lines_data['spread']:
                    score_diff = home_score - away_score
                    if score_diff > 0:
                        # Home team is leading, so give handicap to away team
                        lines_data['spread'] = round(score_diff + 3.5, 1)  # Add safety margin
                    else:
                        # Away team is leading, give handicap to home team
                        lines_data['spread'] = round(score_diff - 3.5, 1)  # Add safety margin
                
                # If we don't have total, try to estimate based on score and quarter
                if not lines_data['total']:
                    current_total = home_score + away_score
                    quarter = int(lines_data['quarter'] or 0)
                    
                    if quarter > 0:
                        # Estimate final total based on current quarter
                        quarters_left = 4 - quarter
                        estimated_final = current_total * (4 / quarter)
                        
                        # Add 5% to estimate
                        lines_data['total'] = round(estimated_final * 1.05, 1)
            except (ValueError, IndexError, TypeError, ZeroDivisionError) as e:
                logger.warning(f"Error calculating lines from score: {str(e)}")
        
        # Calculate total based on league average points if we still don't have it
        if not lines_data['total'] and 'league' in game:
            league_name = game.get('league', {}).get('name', '').lower()
            
            # Data based on league averages
            league_average_points = {
                'nba': 224.5,
                'euroleague': 158.5,
                'eurocup': 162.0,
                'spain': 156.0,
                'greece': 150.0,
                'italy': 154.0,
                'israel': 160.0,
                'turkey': 158.0,
                'lithuania': 152.0,
                'germany': 158.0,
                'france': 152.0,
                'portugal': 150.0,
                'qatar': 148.0
            }
            
            # Default if no specific league average
            default_total = 155.0
            
            # Search for partial match to league name
            for league_key, avg_points in league_average_points.items():
                if league_key in league_name:
                    lines_data['total'] = avg_points
                    break
            
            # If no match found, use default
            if not lines_data['total']:
                lines_data['total'] = default_total
    
    # Round values to nearest half (common in betting)
    if lines_data['spread']:
        lines_data['spread'] = round(lines_data['spread'] * 2) / 2
    
    if lines_data['total']:
        lines_data['total'] = round(lines_data['total'] * 2) / 2
    
    return lines_data

# Function to calculate opportunities
def calculate_opportunities(game_id, current_lines):
    try:
        history = get_game_lines_history(game_id)
        
        if not history or len(history) < 2:
            return None
        
        # Get opening line (first in history)
        opening_lines = history[0]
        
        # Current
        current_spread = current_lines.get('spread')
        current_total = current_lines.get('total')
        
        # Opening
        opening_spread = opening_lines.get('spread')
        opening_total = opening_lines.get('total')
        
        # Calculate differences
        spread_diff = 0
        total_diff = 0
        
        if current_spread is not None and opening_spread is not None:
            spread_diff = current_spread - opening_spread
        
        if current_total is not None and opening_total is not None:
            total_diff = current_total - opening_total
        
        # Identify opportunities based on rules
        opportunity_type = 'neutral'
        opportunity_reason = ''
        
        if abs(spread_diff) >= 7:
            opportunity_type = 'green'
            opportunity_reason = f'Significant spread movement: {spread_diff:.1f} points'
        elif abs(total_diff) >= 10:
            opportunity_type = 'green'
            opportunity_reason = f'Significant total movement: {total_diff:.1f} points'
        
        return {
            'type': opportunity_type,
            'reason': opportunity_reason,
            'spread_diff': spread_diff,
            'total_diff': total_diff,
            'time_status': current_lines.get('time_status'),
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error calculating opportunities for game {game_id}: {str(e)}")
        return {
            'type': 'neutral',
            'reason': '',
            'spread_diff': 0,
            'total_diff': 0,
            'time_status': current_lines.get('time_status'),
            'timestamp': datetime.now().isoformat()
        }

# Function to add opportunity and line info to a game
def add_opportunity_and_lines_to_game(game, opportunity):
    try:
        history = get_game_lines_history(game.get('id', ''))
        
        # Add line information
        if history:
            # Opening line (first in history)
            opening_lines = history[0]
            
            # Start line (if available)
            start_lines = history[1] if len(history) > 1 else opening_lines
            
            # Current line (last in history)
            current_lines = history[-1]
            
            # Add line data to game
            game['opening_spread'] = opening_lines.get('spread')
            game['opening_total'] = opening_lines.get('total')
            
            game['start_spread'] = start_lines.get('spread')
            game['start_total'] = start_lines.get('total')
            
            game['live_spread'] = current_lines.get('spread')
            game['live_total'] = current_lines.get('total')
            
            # Calculate differences
            if game['opening_spread'] is not None and game['live_spread'] is not None:
                game['live_spread_diff'] = game['live_spread'] - game['opening_spread']
            else:
                game['live_spread_diff'] = 0
                
            if game['opening_total'] is not None and game['live_total'] is not None:
                game['live_total_diff'] = game['live_total'] - game['opening_total']
            else:
                game['live_total_diff'] = 0
                
            # Set movement direction
            game['spread_direction'] = 'up' if game.get('live_spread_diff', 0) > 0 else 'down' if game.get('live_spread_diff', 0) < 0 else 'neutral'
            game['total_direction'] = 'up' if game.get('live_total_diff', 0) > 0 else 'down' if game.get('live_total_diff', 0) < 0 else 'neutral'
            
            # Mark significant changes
            game['spread_flag'] = 'green' if abs(game.get('live_spread_diff', 0)) >= 7 else 'neutral'
            game['ou_flag'] = 'green' if abs(game.get('live_total_diff', 0)) >= 10 else 'neutral'
            
            # Mark opening vs start
            if game['opening_spread'] is not None and game['start_spread'] is not None:
                opening_vs_start_spread = game['start_spread'] - game['opening_spread']
                game['opening_vs_start'] = 'green' if abs(opening_vs_start_spread) >= 1 else 'neutral'
            else:
                game['opening_vs_start'] = 'neutral'
        else:
            # If no history, set default values
            game['opening_spread'] = None
            game['opening_total'] = None
            game['start_spread'] = None
            game['start_total'] = None
            game['live_spread'] = None
            game['live_total'] = None
            game['live_spread_diff'] = 0
            game['live_total_diff'] = 0
            game['spread_direction'] = 'neutral'
            game['total_direction'] = 'neutral'
            game['spread_flag'] = 'neutral'
            game['ou_flag'] = 'neutral'
            game['opening_vs_start'] = 'neutral'
        
        # Add opportunity information
        if opportunity:
            game['opportunity_type'] = opportunity.get('type', 'neutral')
            game['opportunity_reason'] = opportunity.get('reason', '')
        else:
            game['opportunity_type'] = 'neutral'
            game['opportunity_reason'] = ''
    except Exception as e:
        logger.error(f"Error adding info to game: {str(e)}")
        # Set default values
        game['opportunity_type'] = 'neutral'
        game['opportunity_reason'] = ''

# API Routes
@app.route('/')
def index():
    # Return index.html from templates directory
    return render_template('index.html')

@app.route('/api/games')
def get_games():
    # Call the B365 API and return data
    params = {
        "sport_id": SPORT_ID,
        "token": B365_TOKEN,
        "_t": int(time.time())  # Prevent caching
    }
    
    logger.info(f"Making API call to B365: {B365_API_URL}")
    
    try:
        response = requests.get(B365_API_URL, params=params, timeout=15)
        logger.info(f"Received response from B365 with status: {response.status_code}")
        
        if response.status_code != 200:
            error_msg = f"Error calling API: status {response.status_code}"
            logger.error(error_msg)
            return jsonify({"error": error_msg, "details": response.text[:200]}), 500
        
        try:
            games_data = response.json()
        except Exception as e:
            error_msg = f"Error parsing JSON: {str(e)}"
            logger.error(error_msg)
            return jsonify({"error": error_msg, "details": response.text[:200]}), 500
        
        # Check if there are results
        if 'results' not in games_data or not games_data['results']:
            logger.warning("No results from B365 API")
            return jsonify({"warning": "No games available now", "raw_data": games_data}), 200
        
        # Count games by status
        live_count = sum(1 for g in games_data['results'] if g.get('time_status') == '1')
        upcoming_count = sum(1 for g in games_data['results'] if g.get('time_status') == '0')
        
        logger.info(f"Received {len(games_data['results'])} games, {live_count} live and {upcoming_count} upcoming")
        
        # Process game data and save lines
        processed_games = 0
        error_games = 0
        
        for game in games_data['results']:
            game_id = game.get('id')
            if not game_id:
                logger.warning(f"Found game without ID")
                continue
                
            try:
                # Extract line data
                lines_data = extract_lines_from_game(game)
                
                # Save lines to history
                try:
                    data_changed = save_game_lines(game_id, lines_data)
                except Exception as e:
                    logger.error(f"Error saving line data for game {game_id}: {str(e)}")
                    data_changed = False
                
                # Calculate opportunities only if data changed
                if data_changed:
                    try:
                        opportunity = calculate_opportunities(game_id, lines_data)
                        if opportunity and opportunity['type'] != 'neutral':
                            save_opportunity(game_id, opportunity)
                    except Exception as e:
                        logger.error(f"Error calculating opportunities for game {game_id}: {str(e)}")
                
                # Get existing opportunity if any
                try:
                    opportunity = get_opportunity(game_id)
                except Exception as e:
                    logger.error(f"Error reading opportunities for game {game_id}: {str(e)}")
                    opportunity = None
                
                # Add information about opportunities and lines to the game
                try:
                    add_opportunity_and_lines_to_game(game, opportunity)
                except Exception as e:
                    logger.error(f"Error adding opportunity data to game {game_id}: {str(e)}")
                
                processed_games += 1
            except Exception as e:
                logger.error(f"General error processing game {game_id}: {str(e)}")
                error_games += 1
        
        logger.info(f"Data processing completed: {processed_games} games processed successfully, {error_games} failed")
        
        # Add additional info to the response
        response_data = games_data.copy()
        response_data['_meta'] = {
            'processed': processed_games,
            'errors': error_games,
            'timestamp': datetime.now().isoformat()
        }
        
        # Set cache control headers
        response = jsonify(response_data)
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response
    except Exception as e:
        error_msg = f"Error calling API: {str(e)}"
        logger.error(error_msg)
        return jsonify({"error": error_msg}), 500

@app.route('/api/game/<game_id>')
def get_game_details(game_id):
    # Call the B365 API for a specific game
    params = {
        "event_id": game_id,
        "token": B365_TOKEN
    }
    
    try:
        response = requests.get(B365_API_URL, params=params, timeout=15)
        logger.info(f"Received response for game {game_id} with status: {response.status_code}")
        
        if response.status_code != 200:
            error_msg = f"Error calling API for game {game_id}: status {response.status_code}"
            logger.error(error_msg)
            return jsonify({"error": error_msg}), 500
        
        try:
            game_data = response.json()
        except Exception as e:
            error_msg = f"Error parsing JSON for game {game_id}: {str(e)}"
            logger.error(error_msg)
            return jsonify({"error": error_msg}), 500
        
        # Add additional info about lines and opportunities
        if 'results' in game_data and game_data['results']:
            game = game_data['results'][0]
            
            # Get existing opportunity if any
            try:
                opportunity = get_opportunity(game_id)
            except Exception as e:
                logger.error(f"Error reading opportunities for game {game_id}: {str(e)}")
                opportunity = None
            
            # Add information about opportunities and lines to the game
            try:
                add_opportunity_and_lines_to_game(game, opportunity)
            except Exception as e:
                logger.error(f"Error adding opportunity data to game {game_id}: {str(e)}")
        
        return jsonify(game_data)
    except Exception as e:
        error_msg = f"Error reading game details {game_id}: {str(e)}"
        logger.error(error_msg)
        return jsonify({"error": error_msg}), 500

@app.route('/api/game/<game_id>/lines_history')
def get_lines_history(game_id):
    try:
        history = get_game_lines_history(game_id)
        return jsonify(history)
    except Exception as e:
        logger.error(f"Error reading lines history for game {game_id}: {str(e)}")
        return jsonify([])

# נקודת קצה חדשה לקבלת ליינים למשחק ספציפי
@app.route('/api/game/<game_id>/odds')
def get_game_odds(game_id):
    try:
        # בדיקה אם game_id הוא למעשה bet365_id
        if game_id.isdigit():
            # נסה להביא נתונים מ-API הייעודי
            odds_data = fetch_odds_data(game_id)
            
            if odds_data:
                # עיבוד הליינים לפורמט פשוט יותר
                formatted_odds = {
                    "spread": None,
                    "total": None,
                    "timestamp": datetime.now().isoformat()
                }
                
                if 'results' in odds_data:
                    for market in odds_data['results']:
                        # חילוץ ספרד
                        if market.get('market_id') == '18_1':
                            for odd in market.get('odds', []):
                                if 'handicap' in odd:
                                    try:
                                        formatted_odds['spread'] = float(odd['handicap'])
                                        break
                                    except (ValueError, TypeError):
                                        pass
                        
                        # חילוץ טוטאל
                        elif market.get('market_id') == '18_2':
                            for odd in market.get('odds', []):
                                if 'handicap' in odd and odd.get('name') == 'Over':
                                    try:
                                        formatted_odds['total'] = float(odd['handicap'])
                                        break
                                    except (ValueError, TypeError):
                                        pass
                
                return jsonify(formatted_odds)
        
        return jsonify({"error": "Odds data not available"}), 404
    except Exception as e:
        logger.error(f"Error fetching odds for game {game_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats')
def get_stats():
    # Calculate statistics from opportunities
    try:
        opportunities = {}
        if os.path@app.route('/api/stats')
def get_stats():
    # Calculate statistics from opportunities
    try:
        opportunities = {}
        if os.path.exists(OPPORTUNITIES_FILE):
            try:
                with open(OPPORTUNITIES_FILE, 'r') as f:
                    opportunities = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                opportunities = {}
        
        # Count opportunities by type
        green_opportunities = sum(1 for opp in opportunities.values() if opp and opp.get('type') == 'green')
        red_opportunities = sum(1 for opp in opportunities.values() if opp and opp.get('type') == 'red')
        blue_opportunities = sum(1 for opp in opportunities.values() if opp and opp.get('type') == 'blue')
        
        # Calculate opportunity percentage
        total_opportunities = green_opportunities + red_opportunities + blue_opportunities
        total_games = max(len(opportunities), 1)  # Prevent division by zero
        opportunity_percentage = round((total_opportunities / total_games * 100) if total_games > 0 else 0)
        
        # Count live and upcoming games from real-time API data
        total_live = 0
        total_upcoming = 0
        
        try:
            # Call the API to get current game data
            params = {
                "sport_id": SPORT_ID,
                "token": B365_TOKEN
            }
            response = requests.get(B365_API_URL, params=params, timeout=10)
            if response.status_code == 200:
                games_data = response.json()
                if 'results' in games_data:
                    # Count games by status
                    for game in games_data['results']:
                        status = game.get('time_status')
                        if status == '1':  # Live game
                            total_live += 1
                        elif status == '0':  # Upcoming game
                            total_upcoming += 1
        except Exception as e:
            logger.error(f"Error counting games: {str(e)}")
            # If error, show at least the number of games in our history
            total_live = sum(1 for game_id, opps in opportunities.items() if opps.get('time_status') == '1')
            total_upcoming = sum(1 for game_id, opps in opportunities.items() if opps.get('time_status') == '0')
        
        stats = {
            "opportunity_percentage": opportunity_percentage,
            "green_opportunities": green_opportunities,
            "red_opportunities": red_opportunities,
            "blue_opportunities": blue_opportunities,
            "total_live": total_live,
            "total_upcoming": total_upcoming
        }
        
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error calculating statistics: {str(e)}")
        return jsonify({
            "opportunity_percentage": 0,
            "green_opportunities": 0,
            "red_opportunities": 0,
            "blue_opportunities": 0,
            "total_live": 0,
            "total_upcoming": 0
        })

@app.route('/api/health')
def health_check():
    """System health check"""
    # Basic check for B365 API
    try:
        response = requests.get(B365_API_URL, params={"token": B365_TOKEN, "sport_id": SPORT_ID}, timeout=5)
        api_status = response.status_code == 200
    except Exception as e:
        logger.error(f"Error in API check: {str(e)}")
        api_status = False
    
    return jsonify({
        "status": "ok" if is_config_valid and api_status else "error",
        "config_valid": is_config_valid,
        "api_available": api_status,
        "environment": "production" if 'RENDER' in os.environ else "development",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/check-b365')
def check_b365():
    """Manual check of B365 API"""
    try:
        logger.info("Starting manual check of B365 API")
        response = requests.get(B365_API_URL, params={"token": B365_TOKEN, "sport_id": SPORT_ID}, timeout=10)
        
        logger.info(f"Received response with status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if 'results' in data and data['results']:
                live_count = sum(1 for g in data['results'] if g.get('time_status') == '1')
                upcoming_count = sum(1 for g in data['results'] if g.get('time_status') == '0')
                
                return jsonify({
                    "status": "ok",
                    "total_games": len(data['results']),
                    "live_games": live_count,
                    "upcoming_games": upcoming_count,
                    "first_game_sample": data['results'][0] if data['results'] else None,
                    "timestamp": datetime.now().isoformat()
                })
            else:
                return jsonify({
                    "status": "no_games",
                    "message": "API connection successful but no games found",
                    "raw_response": data,
                    "timestamp": datetime.now().isoformat()
                })
        else:
            return jsonify({
                "status": "error",
                "message": f"Error connecting to API: {response.status_code}",
                "response_text": response.text[:500],
                "timestamp": datetime.now().isoformat()
            })
    except Exception as e:
        logger.error(f"Error in manual B365 check: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error connecting to API: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })

# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
