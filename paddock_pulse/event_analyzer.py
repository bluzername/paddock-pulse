"""
Event Analyzer Module

This module is responsible for analyzing Formula 1 data using LLMs via OpenRouter.
It identifies interesting events and storylines from the F1 data.
"""

import os
import logging
import json
import requests
from datetime import datetime
import time

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("event_analyzer")

class F1EventAnalyzer:
    """
    Class to analyze F1 data using LLM to identify interesting events.
    """
    
    def __init__(self, api_key="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", save_dir='data'):
        """
        Initialize the F1EventAnalyzer.
        
        Args:
            api_key: OpenRouter API key (defaults to environment variable)
            save_dir: Directory to save the analysis results
        """
        self.api_key = api_key or os.environ.get('OPENROUTER_API_KEY')
        if not self.api_key:
            logger.warning("No OpenRouter API key provided. Please set OPENROUTER_API_KEY environment variable.")
        
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)
        logger.info(f"F1EventAnalyzer initialized with save directory: {save_dir}")
    
    def _prepare_f1_context(self, f1_data):
        """
        Prepare a context string from F1 data for the LLM.
        
        Args:
            f1_data: The F1 data dictionary
            
        Returns:
            A formatted string with the most relevant F1 data
        """
        context = []
        
        # Include current season info
        current_season = f1_data.get('current_season', {})
        if current_season:
            season_year = current_season.get('Season', datetime.now().year)
            context.append(f"CURRENT F1 SEASON: {season_year}")
            
            # Add most recent race info
            recent_race = current_season.get('MostRecentRace', {})
            if recent_race:
                context.append("\nMOST RECENT RACE:")
                context.append(f"Event: {recent_race.get('EventName', 'Unknown')}")
                context.append(f"Circuit: {recent_race.get('Circuit', 'Unknown')}")
                context.append(f"Date: {recent_race.get('Date', 'Unknown')}")
                
                # Add top 10 results
                results = recent_race.get('Results', [])
                if results:
                    context.append("\nTOP 10 RESULTS:")
                    for i, result in enumerate(results[:10]):
                        context.append(f"{i+1}. {result.get('FullName', 'Unknown')} ({result.get('TeamName', 'Unknown')}) - {result.get('Status', 'Unknown')}")
                
                # Add driver details
                drivers = recent_race.get('Drivers', {})
                if drivers:
                    context.append("\nDRIVER PERFORMANCES:")
                    for code, info in list(drivers.items())[:10]:  # Top 10 drivers for brevity
                        context.append(f"{code}: P{info.get('Position', '?')} - {info.get('FullName', 'Unknown')} ({info.get('Team', 'Unknown')})")
            
            # Add championship standings
            standings = current_season.get('Standings', {})
            if standings:
                driver_standings = standings.get('DriverStandings', [])
                if driver_standings:
                    context.append("\nDRIVER CHAMPIONSHIP STANDINGS (TOP 10):")
                    for i, driver in enumerate(driver_standings[:10]):
                        context.append(f"{i+1}. {driver.get('FullName', 'Unknown')} ({driver.get('TeamName', 'Unknown')}) - {driver.get('Points', '0')} points")
                
                team_standings = standings.get('TeamStandings', [])
                if team_standings:
                    context.append("\nTEAM CHAMPIONSHIP STANDINGS:")
                    for i, team in enumerate(team_standings):
                        context.append(f"{i+1}. {team.get('TeamName', 'Unknown')} - {team.get('Points', '0')} points")
        
        # Include historical data summary
        historical_data = f1_data.get('historical_data', {})
        if historical_data:
            context.append("\nHISTORICAL CONTEXT:")
            
            for year, year_data in historical_data.items():
                standings = year_data.get('Standings', {})
                if standings:
                    driver_champ = None
                    team_champ = None
                    
                    driver_standings = standings.get('DriverStandings', [])
                    if driver_standings and len(driver_standings) > 0:
                        driver_champ = driver_standings[0].get('FullName', 'Unknown')
                    
                    team_standings = standings.get('TeamStandings', [])
                    if team_standings and len(team_standings) > 0:
                        team_champ = team_standings[0].get('TeamName', 'Unknown')
                    
                    if driver_champ and team_champ:
                        context.append(f"{year} Champions: {driver_champ} (Driver) and {team_champ} (Team)")
        
        return "\n".join(context)
    
    def analyze_f1_data(self, f1_data, max_events=10, technical_mode=False):
        """
        Analyze F1 data to identify interesting events.
        
        Args:
            f1_data: The F1 data dictionary
            max_events: Maximum number of events to identify
            technical_mode: Whether to focus on technical telemetry data analysis
            
        Returns:
            List of interesting events and their descriptions
        """
        if not self.api_key:
            logger.error("OpenRouter API key not provided")
            return []
        
        # Prepare context for the LLM
        context = self._prepare_f1_context(f1_data)
        
        # Create the prompt for the LLM
        if technical_mode:
            prompt = f"""You are a Formula 1 technical analyst and data scientist. I'll provide you with recent F1 data, and your task is to identify the most interesting technical insights, performance patterns, and telemetry-based observations.

For each technical insight, provide:
1. A technical title that appeals to engineering and data-oriented F1 fans
2. A detailed description incorporating specific technical metrics like tire degradation, fuel consumption, downforce levels, engine performance, etc.
3. Why this technical aspect is significant in the context of car development, race strategy, or season evolution
4. Relevant statistics, lap times, sector comparisons, or telemetry data points that make this noteworthy
5. Mention the respective circuit characteristics (high/low downforce, brake-heavy, etc.) and how they influenced the technical performance
6. Include specific numerical data whenever possible (lap time deltas, top speeds, tire wear percentages, etc.)

Please identify exactly {max_events} technical insights or performance patterns.

Here's the F1 data:

{context}

Format your response as a JSON array with the following structure:
[
  {{
    "title": "Technical Title",
    "description": "Detailed technical description with specific metrics",
    "significance": "Why this technical aspect is significant",
    "stats": "Precise numerical data and statistics",
    "circuit": "Circuit name and characteristics",
    "country": "Country name",
    "weather": "Weather conditions and how they affected performance"
  }},
  ...
]
"""
        else:
            prompt = f"""You are a Formula 1 expert and analyst. I'll provide you with recent F1 data, and your task is to identify the most interesting events, developments, or storylines.

For each event, provide:
1. A title
2. A detailed description of what happened
3. Why it's significant in the context of the current season or F1 history
4. Any relevant statistics or facts that make this noteworthy
5. Mention the respective circuit and country as well as the weather conditions

Please identify exactly {max_events} interesting events or storylines.

Here's the F1 data:

{context}

Format your response as a JSON array with the following structure:
[
  {{
    "title": "Event Title",
    "description": "Detailed description of what happened",
    "significance": "Why this is significant",
    "stats": "Relevant statistics or facts",
    "circuit": "Circuit name",
    "country": "Country name",
    "weather": "Weather conditions"
  }},
  ...
]
"""
        
        logger.info(f"Sending request to OpenRouter to analyze F1 data (max events: {max_events}, technical mode: {technical_mode})")
        
        # Call OpenRouter API
        response = self._call_openai_api(prompt)
        
        # Parse the response
        events = self._parse_events_from_response(response)
        
        # Limit to max_events
        events = events[:max_events]
        
        # Save the results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mode_suffix = "_technical" if technical_mode else ""
        results_path = os.path.join(self.save_dir, f'f1_analysis{mode_suffix}_{timestamp}.json')
        
        with open(results_path, 'w') as f:
            json.dump(events, f, indent=2)
        
        logger.info(f"Analysis saved to {results_path}")
        return events

    def _call_openai_api(self, prompt):
        """
        Call the OpenAI API with the given prompt.
        
        Args:
            prompt: The prompt to send to the API
            
        Returns:
            dict: The API response
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        data = {
            "model": "meta-llama/llama-4-maverick",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            # This explicitly tells the API to return JSON format
            "response_format": {"type": "json_object"}
        }
        
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '{}')
                
                # Try to extract the JSON part from the response
                import re
                
                # First, look for JSON array pattern
                json_array_pattern = r'\[\s*\{.*\}\s*\]'
                array_match = re.search(json_array_pattern, content, re.DOTALL)
                
                if array_match:
                    return array_match.group(0)
                
                # If no array found, return the content as-is
                return content
            else:
                logger.error(f"Error from OpenRouter API: {response.status_code}, {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Exception when calling OpenRouter API: {str(e)}")
            return None
            
    def _parse_events_from_response(self, response):
        """
        Parse the API response into a list of events.
        
        Args:
            response: The API response string
            
        Returns:
            list: List of event dictionaries
        """
        if not response:
            return []
            
        try:
            # First, let's strip any leading or trailing whitespace
            response = response.strip()
            
            # Check for markdown code block markers
            if response.startswith('```json'):
                response = response[7:]  # Remove ```json
            elif response.startswith('```'):
                response = response[3:]  # Remove ``` (generic code block)
            
            if response.endswith('```'):
                response = response[:-3]  # Remove ```
            
            response = response.strip()
            
            # Look for the beginning of a JSON array
            if not response.startswith('['):
                start_idx = response.find('[')
                if start_idx >= 0:
                    response = response[start_idx:]
            
            # Find the closing bracket of the JSON array
            if response.startswith('['):
                end_idx = response.rfind(']')
                if end_idx > 0:
                    response = response[:end_idx+1]
            
            # Parse the JSON content
            content_data = json.loads(response)
            
            # Check if the content is directly an array or if it's inside a property
            if isinstance(content_data, list):
                events = content_data
            else:
                # Look for an array in any of the top-level properties
                events = []
                for value in content_data.values():
                    if isinstance(value, list) and len(value) > 0:
                        events = value
                        break
                
                if not events:
                    # If we can't find an array, just use the whole response
                    events = [content_data]
            
            # Ensure all events have the required fields
            for event in events:
                if "circuit" not in event:
                    event["circuit"] = "N/A"
                if "country" not in event:
                    event["country"] = "N/A"
                if "weather" not in event:
                    event["weather"] = "N/A"
                    
            return events
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from LLM response: {str(e)}")
            logger.error(f"Response content: {response}")
            
            # Last resort: try to find JSON within the text using improved regex pattern
            import re
            
            # Try different patterns to match JSON arrays
            json_patterns = [
                r'\[\s*\{.*?\}\s*\]',  # Standard array pattern
                r'\[\s*\{.*\}\s*\]',    # Greedy array pattern
                r'\{\s*"[^"]+"\s*:\s*\[.*?\]\s*\}'  # Object with array pattern
            ]
            
            potential_json = None
            for pattern in json_patterns:
                matches = re.search(pattern, response, re.DOTALL)
                if matches:
                    potential_json = matches.group(0)
                    try:
                        # Try to parse it - if successful, break the loop
                        json.loads(potential_json)
                        break
                    except json.JSONDecodeError:
                        # Try the next pattern if this one didn't work
                        continue
            
            if potential_json:
                try:
                    content_data = json.loads(potential_json)
                    
                    events = content_data if isinstance(content_data, list) else [content_data]
                    
                    # Ensure all events have the required fields
                    for event in events:
                        if "circuit" not in event:
                            event["circuit"] = "N/A"
                        if "country" not in event:
                            event["country"] = "N/A"
                        if "weather" not in event:
                            event["weather"] = "N/A"
                            
                    logger.info(f"Successfully recovered JSON with regex pattern")
                    return events
                except Exception as inner_e:
                    logger.error(f"Regex recovery attempt failed: {str(inner_e)}")
            
            # If we're still here, try one last approach - extract each "event"
            # from the text using a more forgiving pattern for individual objects
            try:
                obj_pattern = r'\{\s*"title"\s*:.*?\}\s*(?:,|\]|$)'
                matches = re.findall(obj_pattern, response, re.DOTALL)
                
                if matches:
                    events = []
                    for match in matches:
                        # Clean up the match to make it valid JSON
                        clean_match = match.rstrip(',').rstrip(']').strip()
                        if not clean_match.endswith('}'):
                            clean_match += '}'
                            
                        try:
                            event = json.loads(clean_match)
                            # Ensure required fields
                            if "circuit" not in event:
                                event["circuit"] = "N/A"
                            if "country" not in event:
                                event["country"] = "N/A"
                            if "weather" not in event:
                                event["weather"] = "N/A"
                            events.append(event)
                        except:
                            # Skip this match if it can't be parsed
                            continue
                    
                    if events:
                        logger.info(f"Successfully recovered {len(events)} events with object pattern")
                        return events
            except Exception as final_e:
                logger.error(f"Final recovery attempt failed: {str(final_e)}")
            
            return []

if __name__ == "__main__":
    # Simple test when run directly
    from paddock_pulse.f1_data_fetcher import F1DataFetcher
    
    fetcher = F1DataFetcher()
    data = fetcher.load_data()
    
    if data:
        analyzer = F1EventAnalyzer()
        events = analyzer.analyze_f1_data(data)
        print(f"Identified {len(events)} interesting F1 events")
    else:
        print("No F1 data available. Run f1_data_fetcher.py first to fetch data.") 