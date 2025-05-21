// משתנים גלובליים
let liveGames = [];
let refreshInterval;

// כאשר הדף נטען
document.addEventListener('DOMContentLoaded', function() {
    // טען משחקים בפעם הראשונה
    fetchLiveGames();
    
    // טען סטטיסטיקות
    fetchStats();
    
    // הגדר רענון אוטומטי כל 30 שניות
    refreshInterval = setInterval(() => {
        fetchLiveGames();
        fetchStats();
    }, 30000);
    
    // הוסף מאזין לכפתור הרענון הידני
    document.getElementById('refresh-button').addEventListener('click', function() {
        this.querySelector('i').classList.add('rotating');
        
        Promise.all([fetchLiveGames(), fetchStats()])
            .finally(() => {
                setTimeout(() => {
                    this.querySelector('i').classList.remove('rotating');
                }, 500);
            });
    });
});

/**
 * מביא משחקים חיים מהשרת ומציג אותם
 */
function fetchLiveGames() {
    const gamesContainer = document.getElementById('games-container');
    
    // הצג הודעת טעינה אם אין משחקים
    if (!liveGames.length) {
        gamesContainer.innerHTML = '<div class="loading">טוען משחקים...</div>';
    }
    
    return fetch('/api/games')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            if (data.results && Array.isArray(data.results)) {
                liveGames = data.results;
                displayGames(liveGames);
            } else {
                gamesContainer.innerHTML = '<div class="no-games">אין משחקים חיים כרגע</div>';
            }
        })
        .catch(error => {
            console.error('Error fetching live games:', error);
            gamesContainer.innerHTML = '<div class="no-games">אירעה שגיאה בטעינת המשחקים. נסה שוב מאוחר יותר.</div>';
        });
}

/**
 * מביא סטטיסטיקות מהשרת ומציג אותן
 */
function fetchStats() {
    return fetch('/api/stats')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(stats => {
            // עדכן את הסטטיסטיקות בממשק
            document.getElementById('total-live').textContent = stats.total_live || 0;
            document.getElementById('opportunity-percentage').textContent = `${stats.opportunity_percentage || 0}%`;
        })
        .catch(error => {
            console.error('Error fetching stats:', error);
        });
}

/**
 * מציג את המשחקים החיים בדף
 * @param {Array} games - רשימת משחקים
 */
function displayGames(games) {
    const gamesContainer = document.getElementById('games-container');
    
    // אם אין משחקים, הצג הודעה
    if (!games || games.length === 0) {
        gamesContainer.innerHTML = '<div class="no-games">אין משחקים חיים כרגע</div>';
        return;
    }
    
    // מיין משחקים לפי ליגות
    const gamesByLeague = groupGamesByLeague(games);
    
    // נקה את המכולה
    gamesContainer.innerHTML = '';
    
    // עבור על כל ליגה והוסף את המשחקים שלה
    for (const league in gamesByLeague) {
        const leagueGames = gamesByLeague[league];
        
        // צור כותרת ליגה
        const leagueHeader = document.createElement('div');
        leagueHeader.className = 'league-header';
        leagueHeader.textContent = league;
        gamesContainer.appendChild(leagueHeader);
        
        // צור מכולה למשחקי הליגה
        const leagueContainer = document.createElement('div');
        leagueContainer.className = 'league-games';
        
        // הוסף כל משחק בליגה
        leagueGames.forEach(game => {
            const gameElement = createGameElement(game);
            leagueContainer.appendChild(gameElement);
        });
        
        gamesContainer.appendChild(leagueContainer);
    }
}

/**
 * מקבץ משחקים לפי ליגה
 * @param {Array} games - רשימת משחקים
 * @returns {Object} - אובייקט עם משחקים מקובצים לפי ליגה
 */
function groupGamesByLeague(games) {
    const gamesByLeague = {};
    
    games.forEach(game => {
        const league = game.league?.name || 'ליגה לא ידועה';
        
        if (!gamesByLeague[league]) {
            gamesByLeague[league] = [];
        }
        
        gamesByLeague[league].push(game);
    });
    
    return gamesByLeague;
}

/**
 * יוצר אלמנט HTML עבור משחק
 * @param {Object} game - נתוני המשחק
 * @returns {HTMLElement} - אלמנט HTML של המשחק
 */
function createGameElement(game) {
    const gameElement = document.createElement('div');
    gameElement.className = 'game-card';
    gameElement.id = `game-${game.id}`;
    
    // קבע צבע רקע לפי סוג ההזדמנות
    if (game.opportunity_type === 'green') {
        gameElement.classList.add('opportunity-positive');
    } else if (game.opportunity_type === 'red') {
        gameElement.classList.add('opportunity-negative');
    }
    
    // פענח את הזמן והרבע
    const quarter = game.timer?.q || '1';
    const timeRemaining = formatGameTime(game.timer);
    
    // הוסף תוכן HTML למשחק
    gameElement.innerHTML = `
        <div class="game-header">
            <div class="game-period">רבע ${quarter}</div>
            <div class="game-time">${timeRemaining}</div>
            <div class="refresh-odds" onclick="refreshGameOdds('${game.bet365_id}', event)">
                <i class="fas fa-sync-alt"></i>
            </div>
        </div>
        <div class="teams-container">
            <div class="team home-team">
                <div class="team-name">${game.home?.name || 'Home'}</div>
                <div class="team-score">${getScoreFromSs(game, 'home')}</div>
                <div class="team-spread" id="home-spread-${game.id}"></div>
            </div>
            <div class="vs">VS</div>
            <div class="team away-team">
                <div class="team-name">${game.away?.name || 'Away'}</div>
                <div class="team-score">${getScoreFromSs(game, 'away')}</div>
                <div class="team-spread" id="away-spread-${game.id}"></div>
            </div>
        </div>
        <div class="odds-container">
            <div class="total-container">
                <div class="label">סה"כ:</div>
                <div class="total-value" id="total-${game.id}"></div>
                ${getDirectionArrow(game.total_direction)}
            </div>
            <div class="spread-container">
                <div class="label">ספרד:</div>
                <div class="spread-value" id="spread-${game.id}"></div>
                ${getDirectionArrow(game.spread_direction)}
            </div>
        </div>
        ${game.opportunity_reason ? `<div class="opportunity-reason">${game.opportunity_reason}</div>` : ''}
    `;
    
    // עדכן את ערכי הספרד והטוטאל
    updateGameLines(game);
    
    return gameElement;
}

/**
 * מחלץ תוצאה מהמחרוזת ss
 * @param {Object} game - נתוני המשחק
 * @param {string} team - הקבוצה (home/away)
 * @returns {string} - התוצאה
 */
function getScoreFromSs(game, team) {
    if (!game.ss) return '0';
    
    const scores = game.ss.split('-');
    if (scores.length !== 2) return '0';
    
    return team === 'home' ? scores[0] : scores[1];
}

/**
 * מעצב את תצוגת השעון במשחק
 * @param {Object} timer - אובייקט הטיימר
 * @returns {string} - מחרוזת מעוצבת של הזמן
 */
function formatGameTime(timer) {
    if (!timer) return "00:00";
    
    const minutes = parseInt(timer.tm || 0);
    const seconds = parseInt(timer.ts || 0);
    
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
}

/**
 * מחזיר אייקון חץ לפי כיוון
 * @param {string} direction - כיוון (up, down, neutral)
 * @returns {string} - HTML של אייקון חץ
 */
function getDirectionArrow(direction) {
    if (direction === 'up') {
        return '<i class="fas fa-arrow-up up-arrow"></i>';
    } else if (direction === 'down') {
        return '<i class="fas fa-arrow-down down-arrow"></i>';
    }
    return '';
}

/**
 * מעדכן את הליינים (ספרד וטוטאל) למשחק ספציפי
 * @param {Object} game - נתוני המשחק
 */
function updateGameLines(game) {
    // הצגת ספרד
    const homeSpreadElement = document.getElementById(`home-spread-${game.id}`);
    const awaySpreadElement = document.getElementById(`away-spread-${game.id}`);
    const totalElement = document.getElementById(`total-${game.id}`);
    const spreadElement = document.getElementById(`spread-${game.id}`);
    
    if (homeSpreadElement && awaySpreadElement) {
        let homeSpreadDisplay = "-";
        let awaySpreadDisplay = "-";
        let isHomeFavorite = false;
        
        // בדוק אם הספרד הוא הגיוני ואז החלט מי המועדף
        if (game.live_spread !== null && !isNaN(game.live_spread)) {
            const spreadValue = parseFloat(game.live_spread);
            
            // אם יש לנו כיוון ספציפי המציין את העדיפות
            if (game.spread_direction === 'down') {
                // הקבוצה הביתית מועדפת
                isHomeFavorite = true;
                homeSpreadDisplay = `-${Math.abs(spreadValue).toFixed(1)}`;
                awaySpreadDisplay = `+${Math.abs(spreadValue).toFixed(1)}`;
            } else {
                // הקבוצה האורחת מועדפת
                isHomeFavorite = false;
                homeSpreadDisplay = `+${Math.abs(spreadValuefunction updateGameLines(game) {
    // הצגת ספרד
    const homeSpreadElement = document.getElementById(`home-spread-${game.id}`);
    const awaySpreadElement = document.getElementById(`away-spread-${game.id}`);
    const totalElement = document.getElementById(`total-${game.id}`);
    const spreadElement = document.getElementById(`spread-${game.id}`);
    
    if (homeSpreadElement && awaySpreadElement) {
        let homeSpreadDisplay = "-";
        let awaySpreadDisplay = "-";
        let isHomeFavorite = false;
        
        // בדוק אם הספרד הוא הגיוני ואז החלט מי המועדף
        if (game.live_spread !== null && !isNaN(game.live_spread)) {
            const spreadValue = parseFloat(game.live_spread);
            
            // אם יש לנו כיוון ספציפי המציין את העדיפות
            if (game.spread_direction === 'down') {
                // הקבוצה הביתית מועדפת
                isHomeFavorite = true;
                homeSpreadDisplay = `-${Math.abs(spreadValue).toFixed(1)}`;
                awaySpreadDisplay = `+${Math.abs(spreadValue).toFixed(1)}`;
            } else {
                // הקבוצה האורחת מועדפת
                isHomeFavorite = false;
                homeSpreadDisplay = `+${Math.abs(spreadValue).toFixed(1)}`;
                awaySpreadDisplay = `-${Math.abs(spreadValue).toFixed(1)}`;
            }
        }
        
        homeSpreadElement.textContent = homeSpreadDisplay;
        awaySpreadElement.textContent = awaySpreadDisplay;
        
        // עדכון תצוגת ספרד מרכזית אם קיימת
        if (spreadElement) {
            if (game.live_spread !== null && !isNaN(game.live_spread)) {
                spreadElement.textContent = Math.abs(parseFloat(game.live_spread)).toFixed(1);
            } else {
                spreadElement.textContent = "-";
            }
        }
    }
    
    // הצגת טוטאל
    if (totalElement) {
        if (game.live_total !== null && !isNaN(game.live_total)) {
            totalElement.textContent = parseFloat(game.live_total).toFixed(1);
        } else {
            totalElement.textContent = "-";
        }
    }
}

/**
 * מרענן את הליינים עבור משחק ספציפי
 * @param {string} bet365Id - המזהה של המשחק ב-Bet365
 * @param {Event} event - אירוע הלחיצה
 */
function refreshGameOdds(bet365Id, event) {
    // מנע התפשטות האירוע
    if (event) {
        event.stopPropagation();
    }
    
    // הצג אנימציה של טעינה
    const refreshIcon = event.currentTarget.querySelector('i');
    if (refreshIcon) {
        refreshIcon.classList.add('rotating');
    }
    
    fetch(`/api/game/${bet365Id}/odds`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(odds => {
            console.log('Updated odds:', odds);
            
            // מצא את המשחק המתאים
            const game = liveGames.find(g => g.bet365_id === bet365Id);
            
            if (game) {
                // עדכן את ערכי הליינים
                if (odds.spread !== null) {
                    game.live_spread = odds.spread;
                }
                
                if (odds.total !== null) {
                    game.live_total = odds.total;
                }
                
                // עדכן את התצוגה
                updateGameLines(game);
            }
        })
        .catch(error => {
            console.error('Error refreshing odds:', error);
        })
        .finally(() => {
            // הסר את אנימציית הטעינה
            if (refreshIcon) {
                setTimeout(() => {
                    refreshIcon.classList.remove('rotating');
                }, 500);
            }
        });
}

// עצור את הרענון האוטומטי כשהדף נסגר
window.addEventListener('beforeunload', function() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
});
