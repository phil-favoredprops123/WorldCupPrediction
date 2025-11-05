# Data Sources for FIFA World Cup 2026

This document provides detailed information about all data sources configured for the World Cup 2026 probability tracking system.

## Quick Start

1. **Set up API keys:**
   ```bash
   python setup_api_keys.py
   ```

2. **Test your configuration:**
   ```bash
   python setup_api_keys.py test
   ```

3. **Run an update:**
   ```bash
   python update_probabilities.py --match-day 1
   ```

## Confederation Data Sources

### UEFA (Union of European Football Associations)
- **Primary API**: `https://api.uefa.com`
- **Backup API**: `https://api.football-data.org/v4`
- **Free Source**: `https://www.uefa.com`
- **Coverage**: UEFA Nations League, Euro Qualifiers, Champions League
- **Rate Limit**: 1000 requests/hour
- **Data Quality**: Excellent
- **API Key Required**: Yes

### CAF (Confederation of African Football)
- **Primary API**: `https://api.cafonline.com`
- **Backup API**: `https://api.flashscore.com`
- **Free Source**: `https://www.cafonline.com`
- **Coverage**: Africa Cup of Nations, CAF Champions League, World Cup Qualifiers
- **Rate Limit**: 500 requests/hour
- **Data Quality**: Good
- **API Key Required**: Yes

### CONCACAF (North, Central America and Caribbean)
- **Primary API**: `https://api.concacaf.com`
- **Backup API**: `https://api.fotmob.com`
- **Free Source**: `https://www.concacaf.com`
- **Coverage**: CONCACAF Nations League, Gold Cup, World Cup Qualifiers
- **Rate Limit**: 800 requests/hour
- **Data Quality**: Good
- **API Key Required**: Yes

### AFC (Asian Football Confederation)
- **Primary API**: `https://api.the-afc.com`
- **Backup API**: `https://api.sofascore.com`
- **Free Source**: `https://www.the-afc.com`
- **Coverage**: AFC Asian Cup, AFC Champions League, World Cup Qualifiers
- **Rate Limit**: 600 requests/hour
- **Data Quality**: Good
- **API Key Required**: Yes

### CONMEBOL (South American Football Confederation)
- **Primary API**: `https://api.conmebol.com`
- **Backup API**: `https://api.football-data.org/v4`
- **Free Source**: `https://www.conmebol.com`
- **Coverage**: Copa América, Copa Libertadores, World Cup Qualifiers
- **Rate Limit**: 1000 requests/hour
- **Data Quality**: Excellent
- **API Key Required**: Yes

### OFC (Oceania Football Confederation)
- **Primary API**: `https://api.oceaniafootball.com`
- **Backup API**: `https://api.flashscore.com`
- **Free Source**: `https://www.oceaniafootball.com`
- **Coverage**: OFC Nations Cup, OFC Champions League, World Cup Qualifiers
- **Rate Limit**: 300 requests/hour
- **Data Quality**: Moderate
- **API Key Required**: Yes

## Third-Party APIs

### Football-Data.org
- **URL**: `https://api.football-data.org/v4`
- **Free Tier**: 10 requests/minute
- **Paid Tier**: 1000 requests/minute
- **Coverage**: UEFA, CONMEBOL, CONCACAF, AFC
- **Cost**: $20-100/month
- **Registration**: https://www.football-data.org/client/register

### API-Football
- **URL**: `https://v3.football.api-sports.io`
- **Free Tier**: 100 requests/day
- **Paid Tier**: 10000 requests/day
- **Coverage**: All confederations
- **Cost**: $10-50/month
- **Registration**: https://rapidapi.com/api-sports/api/api-football

### SofaScore
- **URL**: `https://api.sofascore.com`
- **Free Tier**: Limited
- **Paid Tier**: Full access
- **Coverage**: All confederations
- **Cost**: $50-200/month
- **Registration**: https://www.sofascore.com/api

### FlashScore
- **URL**: `https://api.flashscore.com`
- **Free Tier**: Basic data
- **Paid Tier**: Full access
- **Coverage**: All confederations
- **Cost**: $30-150/month
- **Registration**: https://www.flashscore.com/api

### ESPN API
- **URL**: `https://site.api.espn.com/apis/site/v2/sports/soccer`
- **Free Tier**: Limited
- **Paid Tier**: Full access
- **Coverage**: All confederations
- **Cost**: $100-500/month
- **Registration**: https://developer.espn.com/

## Data Collection Strategy

### High Priority (Daily Updates)
- **Match Results**: All confederations
- **Group Standings**: Qualifying groups
- **FIFA Rankings**: Monthly updates

### Medium Priority (Weekly Updates)
- **Team Form**: Last 5 matches
- **Head-to-Head Records**: Historical data
- **Injury Reports**: Key player status

### Low Priority (Monthly Updates)
- **Historical Performance**: Past tournaments
- **Tactical Analysis**: Playing style data
- **Weather Data**: Venue conditions

## Fallback Strategy

1. **Primary API fails** → Use backup API
2. **Backup API fails** → Use free source with web scraping
3. **All sources fail** → Use cached data with warning
4. **Cache expires** → Use default values

## Rate Limiting

Each API has specific rate limits:
- **UEFA**: 1000 requests/hour
- **CAF**: 500 requests/hour
- **CONCACAF**: 800 requests/hour
- **AFC**: 600 requests/hour
- **CONMEBOL**: 1000 requests/hour
- **OFC**: 300 requests/hour

The system automatically manages rate limiting and will queue requests when limits are reached.

## Data Quality

### Excellent (UEFA, CONMEBOL)
- Real-time updates
- Comprehensive statistics
- Historical data
- Official sources

### Good (CAF, CONCACAF, AFC)
- Regular updates
- Good statistics
- Some historical data
- Reliable sources

### Moderate (OFC)
- Basic updates
- Limited statistics
- Minimal historical data
- Basic sources

## Cost Optimization

### Free Tier Strategy
1. Start with free tiers
2. Use multiple free sources
3. Implement caching
4. Prioritize high-impact data

### Paid Tier Strategy
1. Focus on high-quality sources
2. Use paid APIs for critical data
3. Implement smart caching
4. Monitor usage and costs

## Monitoring and Alerts

The system includes monitoring for:
- API failures
- Rate limit violations
- Data quality issues
- Cost overruns
- Cache misses

## Troubleshooting

### Common Issues

1. **API Key Invalid**
   - Check key format
   - Verify registration
   - Check expiration

2. **Rate Limit Exceeded**
   - Wait for reset
   - Use backup API
   - Implement queuing

3. **Data Not Found**
   - Check date ranges
   - Verify team names
   - Use fallback sources

4. **Network Errors**
   - Check internet connection
   - Verify API endpoints
   - Use cached data

### Debug Mode

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Support

For issues with specific APIs:
- **FIFA**: https://www.fifa.com/contact
- **UEFA**: https://www.uefa.com/insideuefa/contact
- **Football-Data**: https://www.football-data.org/contact
- **API-Football**: https://rapidapi.com/api-sports/api/api-football/support

## Updates

This configuration is updated regularly as new APIs become available and existing ones change their terms of service.
