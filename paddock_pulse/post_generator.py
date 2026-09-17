"""
Post Generator Module

This module is responsible for generating compelling social media posts
about Formula 1 events using LLMs via OpenRouter.
"""

import os
import logging
import json
import requests
from paddock_pulse import config
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("post_generator")

class F1PostGenerator:
    """
    Class to generate compelling social media posts about F1 events.
    """
    
    def __init__(self, api_key=None, save_dir='output'):
        """
        Initialize the F1PostGenerator.
        
        Args:
            api_key: OpenRouter API key (defaults to environment variable)
            save_dir: Directory to save the generated posts
        """
        self.api_key = api_key or os.environ.get('OPENROUTER_API_KEY')
        if not self.api_key:
            logger.warning("No OpenRouter API key provided. Please set OPENROUTER_API_KEY environment variable.")
        
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)
        logger.info(f"F1PostGenerator initialized with save directory: {save_dir}")
    
    def _clean_text(self, text):
        """
        Clean the text by removing any content in parentheses or square brackets.
        
        Args:
            text: The text to clean
            
        Returns:
            Cleaned text with parentheses and square bracket content removed
        """
        import re
        # Remove content in parentheses and square brackets, including the brackets themselves
        cleaned_text = re.sub(r'\([^)]*\)|\[[^\]]*\]', '', text)
        # Remove any double spaces that might result from the removal
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        return cleaned_text.strip()
    
    def _format_numbers_and_units(self, text):
        """
        Format numbers and units to be more natural for voiceover.
        
        Args:
            text: The text to format
            
        Returns:
            Formatted text with numbers and units in a more natural format
        """
        import re
        
        # Define patterns and replacements
        patterns = [
            # Decimal numbers with units (e.g., "2.34 s" -> "2.34 seconds")
            (r'(\d+\.\d+)\s*s(?=\W|$)', r'\1 seconds'),
            (r'(\d+\.\d+)\s*ms(?=\W|$)', r'\1 milliseconds'),
            (r'(\d+\.\d+)\s*km(?=\W|$)', r'\1 kilometers'),
            (r'(\d+\.\d+)\s*m(?=\W|$)', r'\1 meters'),
            (r'(\d+\.\d+)\s*cm(?=\W|$)', r'\1 centimeters'),
            (r'(\d+\.\d+)\s*mm(?=\W|$)', r'\1 millimeters'),
            (r'(\d+\.\d+)\s*kg(?=\W|$)', r'\1 kilograms'),
            (r'(\d+\.\d+)\s*g(?=\W|$)', r'\1 grams'),
            (r'(\d+\.\d+)\s*°C(?=\W|$)', r'\1 degrees Celsius'),
            (r'(\d+\.\d+)\s*°F(?=\W|$)', r'\1 degrees Fahrenheit'),
            
            # Integer numbers with units (e.g., "320 kmh" -> "320 kilometers per hour")
            (r'(\d+)\s*kmh(?=\W|$)', r'\1 kilometers per hour'),
            (r'(\d+)\s*km/h(?=\W|$)', r'\1 kilometers per hour'),
            (r'(\d+)\s*mph(?=\W|$)', r'\1 miles per hour'),
            (r'(\d+)\s*rpm(?=\W|$)', r'\1 revolutions per minute'),
            (r'(\d+)\s*Hz(?=\W|$)', r'\1 hertz'),
            (r'(\d+)\s*kHz(?=\W|$)', r'\1 kilohertz'),
            (r'(\d+)\s*MHz(?=\W|$)', r'\1 megahertz'),
            (r'(\d+)\s*GB(?=\W|$)', r'\1 gigabytes'),
            (r'(\d+)\s*MB(?=\W|$)', r'\1 megabytes'),
            (r'(\d+)\s*KB(?=\W|$)', r'\1 kilobytes'),
            (r'(\d+)\s*s(?=\W|$)', r'\1 seconds'),
            (r'(\d+)\s*ms(?=\W|$)', r'\1 milliseconds'),
            (r'(\d+)\s*km(?=\W|$)', r'\1 kilometers'),
            (r'(\d+)\s*m(?=\W|$)', r'\1 meters'),
            (r'(\d+)\s*cm(?=\W|$)', r'\1 centimeters'),
            (r'(\d+)\s*mm(?=\W|$)', r'\1 millimeters'),
            (r'(\d+)\s*kg(?=\W|$)', r'\1 kilograms'),
            (r'(\d+)\s*g(?=\W|$)', r'\1 grams'),
            (r'(\d+)\s*°C(?=\W|$)', r'\1 degrees Celsius'),
            (r'(\d+)\s*°F(?=\W|$)', r'\1 degrees Fahrenheit'),
            
            # F1-specific terms
            (r'DRS(?=\W|$)', r'DRS (Drag Reduction System)'),
            (r'ERS(?=\W|$)', r'ERS (Energy Recovery System)'),
            (r'KERS(?=\W|$)', r'KERS (Kinetic Energy Recovery System)'),
            
            # Handle fractions (e.g., "1/10th" -> "one tenth")
            (r'1/2(?=\W|$)', r'one half'),
            (r'1/3(?=\W|$)', r'one third'),
            (r'2/3(?=\W|$)', r'two thirds'),
            (r'1/4(?=\W|$)', r'one quarter'),
            (r'3/4(?=\W|$)', r'three quarters'),
            (r'1/5(?=\W|$)', r'one fifth'),
            (r'1/10(?=\W|$)', r'one tenth'),
            (r'1/100(?=\W|$)', r'one hundredth'),
            
            # Handle ordinals (1st, 2nd, 3rd, etc.)
            (r'(\d+)(st|nd|rd|th)(?=\W|$)', r'\1\2'),
        ]
        
        # Apply all patterns
        formatted_text = text
        for pattern, replacement in patterns:
            formatted_text = re.sub(pattern, replacement, formatted_text)
        
        # Special case for repeated decimals to ensure they're read naturally
        # e.g., "1.23" -> specify that it's "one point two three" not "one point twenty-three"
        def format_decimal_number(match):
            full_number = match.group(0)
            parts = full_number.split('.')
            if len(parts) == 2 and parts[1]:
                # If there are multiple digits after the decimal point
                # and they wouldn't naturally be read digit-by-digit
                if len(parts[1]) > 1 and not (parts[1].startswith('0') or int(parts[1]) <= 20):
                    # Convert to "one point two three" format
                    decimal_part = ' '.join(parts[1])
                    return f"{parts[0]} point {decimal_part}"
            return full_number
        
        # Apply the decimal formatting for standalone numbers (not already handled with units)
        formatted_text = re.sub(r'\b\d+\.\d+\b', format_decimal_number, formatted_text)
        
        return formatted_text
    
    def generate_post(self, event, technical_mode=False):
        """
        Generate a social media post for a single F1 event.
        
        Args:
            event: Dictionary containing event details
            technical_mode: Whether to generate technical content focused on telemetry data
            
        Returns:
            The generated post text
        """
        if not self.api_key:
            logger.error("OpenRouter API key not provided")
            return "API key required to generate posts."
        
        # Create the prompt for the LLM
        if technical_mode:
            prompt = f"""You are a Formula 1 technical data analyst creating a compelling technical commentary about the following F1 event for social media.

Write a short, data-driven analysis in an expert, precise style that would accompany an F1 technical infographic or data visualization. Use the analytical style of F1 technical experts like Craig Scarborough, Gary Anderson, or Pat Symonds.

Your technical commentary should:
- Start with a specific technical aspect or performance metric in the first few words
- Focus heavily on precise data points, percentages, and technical measurements
- Include detailed technical terminology appropriate for knowledgeable F1 fans
- Explain the engineering significance behind the numbers
- Reference specific car components, aerodynamic concepts, or setup choices
- Use technical comparisons with other cars/teams when relevant
- Mention the circuit characteristics that affected this technical aspect
- Keep the tone informative and analytical rather than dramatic
- Be 2-3 sentences (50-70 words) for perfect social media delivery
- Include appropriate technical/data-focused hashtags at the end, separated by a blank line

EVENT TECHNICAL DETAILS:
Title: {event.get('title', 'Unknown event')}
Description: {event.get('description', 'No description available')}
Significance: {event.get('significance', 'N/A')}
Technical Stats: {event.get('stats', 'N/A')}
Circuit: {event.get('circuit', 'Unknown circuit')}
Country: {event.get('country', 'Unknown country')}
Weather: {event.get('weather', 'N/A')}

IMPORTANT: You MUST provide both a technical commentary text AND hashtags. Do not leave either section empty.
The technical commentary should be data-driven and precise, focusing on the engineering aspects of the event.
The hashtags should be relevant to the technical content and include technical F1 terms.

Structure your response EXACTLY as follows:
[Your technical commentary text here]

[Your technical hashtags here]

Do not include any other text or explanations."""
        else:
            prompt = f"""You are a British Formula 1 commentator creating compelling voice commentary about the following F1 event.

Write a short, dramatic narration in authentic British English that would be read aloud over F1 footage. Use the passionate, enthusiastic style of Sky Sports F1 commentators like Martin Brundle, David Croft, or Will Buxton.

Your narration should:
- Start with an iconic F1 entity (driver, team, or track name) in the first few words
- Focus on concrete facts, statistics, and data points rather than metaphors
- Weave location and weather details naturally into the narrative flow
- Use British English spelling and expressions
- Be dynamic, emotional, and immersive with natural speech patterns
- Include dramatic pauses and emphasis where appropriate
- Build excitement and tension through word choice and pacing
- Use present tense to create immediacy
- Focus on the human drama and emotional impact of the event
- Be 2-3 sentences (50-70 words) for perfect spoken delivery
- Include appropriate hashtags at the end, separated by a blank line
- When using numbers and measurements, spell them out fully for spoken delivery
  (e.g., "320 kilometers per hour" not "320 kmh", "2.4 seconds" not "2.4 s")

EVENT DETAILS:
Title: {event.get('title', 'Unknown event')}
Description: {event.get('description', 'No description available')}
Significance: {event.get('significance', 'N/A')}
Statistics: {event.get('stats', 'N/A')}
Location: {event.get('location', 'N/A')}
Weather: {event.get('weather', 'N/A')}

IMPORTANT: You MUST provide both a commentary text AND hashtags. Do not leave either section empty.
The commentary text should be dramatic and engaging, focusing on the key aspects of the event.
The hashtags should be relevant to the event and include the main entities involved.

Structure your response EXACTLY as follows:
[Your dramatic commentary text here]

[Your hashtags here]

Do not include any other text or explanations."""
        
        logger.info(f"Sending request to OpenRouter to generate post about: {event.get('title', 'Unknown event')}")
        
        # Call OpenRouter API
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        data = {
            "model": config.TEXT_MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,  # Add some creativity while maintaining consistency
            "max_tokens": 500    # Ensure we have enough tokens for both text and hashtags
        }
        
        post_text = ""
        hashtags = ""
        max_retries = 2
        current_try = 0
        
        while current_try < max_retries and (not post_text or post_text.startswith("The race was held during")):
            try:
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    full_text = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                    
                    # Split the response into main text and hashtags
                    parts = full_text.strip().split("\n\n")
                    if len(parts) >= 2:
                        post_text = self._clean_text(parts[0].strip())
                        hashtags = self._clean_text(parts[-1].strip())
                    else:
                        # If there's no clear split, try to extract hashtags from the text
                        import re
                        post_text = self._clean_text(full_text.strip())
                        hashtags_matches = re.findall(r'#\w+', post_text)
                        if hashtags_matches:
                            # Remove hashtags from main text if they're at the end
                            clean_text = re.sub(r'(#\w+\s*)+$', '', post_text).strip()
                            if clean_text:  # Only use clean text if it's not empty
                                post_text = clean_text
                            hashtags = ' '.join(hashtags_matches)
                    
                    # If we still don't have proper content, prepare for retry
                    if not post_text or post_text.startswith("The race was held during"):
                        current_try += 1
                        if current_try < max_retries:
                            logger.warning(f"Retry {current_try} for post generation: {event.get('title', 'Unknown event')}")
                            # Modify the prompt slightly for the retry
                            data["messages"][0]["content"] = prompt + "\n\nIMPORTANT: This is a retry. Please ensure you provide both commentary text and hashtags."
                            continue
                else:
                    logger.error(f"Error from OpenRouter API: {response.status_code}, {response.text}")
                    post_text = f"Failed to generate post about {event.get('title', 'Unknown event')}"
                    break
            except Exception as e:
                logger.error(f"Exception when calling OpenRouter API: {str(e)}")
                post_text = f"Error generating post: {str(e)}"
                break
        
        # If we still don't have proper content after retries, create a fallback message
        if not post_text or post_text.startswith("The race was held during"):
            logger.warning(f"Creating fallback content for: {event.get('title', 'Unknown event')}")
            if technical_mode:
                post_text = f"Technical analysis of {event.get('title', 'Unknown event')} reveals critical performance factors. The data shows significant patterns in car behavior that could explain the race outcome. Engineers will be analyzing these metrics closely to optimize future performance."
                hashtags = f"#{event.get('title', 'Unknown event').replace(' ', '')} #F1Tech #F1Data #TelemetryAnalysis"
            else:
                post_text = f"{event.get('title', 'Unknown event')} delivers an exciting performance! The team shows remarkable determination and skill on the track, demonstrating their championship potential. A truly impressive display of Formula 1 racing at its finest!"
                hashtags = f"#{event.get('title', 'Unknown event').replace(' ', '')} #F1 #Formula1 #Racing"
        
        # Format numbers and units for voiceover readability
        post_text = self._format_numbers_and_units(post_text)
        
        return post_text.strip(), hashtags.strip()
    
    def generate_posts_from_events(self, events, max_posts=5, technical_mode=False):
        """
        Generate social media posts from analyzed F1 events.
        
        Args:
            events: List of event dictionaries
            max_posts: Maximum number of posts to generate
            technical_mode: Whether to generate technical content focused on telemetry data
            
        Returns:
            List of generated post texts
        """
        if not events:
            logger.warning("No events provided to generate posts from")
            return []
        
        # Limit the number of events to max_posts
        events_to_process = events[:max_posts]
        logger.info(f"Generating posts for {len(events_to_process)} events")
        
        posts = []
        for i, event in enumerate(events_to_process):
            logger.info(f"Generating post {i+1}/{len(events_to_process)}")
            post_text, hashtags = self.generate_post(event, technical_mode)
            posts.append({
                "event_title": event.get('title', 'Unknown event'),
                "post_text": post_text,
                "hashtags": hashtags,
                "content": f"{post_text}\n\n{hashtags}",  # Double newline for clear separation
                "technical": technical_mode
            })
        
        # Save the generated posts
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mode_suffix = "_technical" if technical_mode else ""
        posts_path = os.path.join(self.save_dir, f'f1_posts{mode_suffix}_{timestamp}.json')
        with open(posts_path, 'w') as f:
            json.dump(posts, f, indent=2)
        
        # Also save as plain text for easy reading
        text_path = os.path.join(self.save_dir, f'f1_posts{mode_suffix}_{timestamp}.txt')
        with open(text_path, 'w') as f:
            for i, post in enumerate(posts):
                f.write(f"Post {i+1}: {post['event_title']}\n")
                f.write(f"{'-' * 50}\n")
                f.write(f"{post['post_text']}\n\n")
                f.write(f"{post['hashtags']}\n\n")
        
        logger.info(f"Generated {len(posts)} posts and saved to {posts_path} and {text_path}")
        return posts

    def generate_f1_101_posts(self, num_topics=5):
        """
        Generate educational posts explaining F1 basics for new fans.
        
        Args:
            num_topics: Number of educational topics to generate
            
        Returns:
            List of generated educational posts
        """
        if not self.api_key:
            logger.error("OpenRouter API key not provided")
            return []
        
        logger.info(f"Generating {num_topics} educational F1 topics for new fans")
        
        # First, get a list of educational topics to cover
        topics = self._generate_f1_101_topics(num_topics)
        if not topics:
            logger.error("Failed to generate F1 educational topics")
            return []
            
        logger.info(f"Generated {len(topics)} educational topics: {', '.join([t['title'] for t in topics])}")
        
        # Generate a detailed post for each topic
        posts = []
        for i, topic in enumerate(topics):
            logger.info(f"Generating educational post {i+1}/{len(topics)}: {topic['title']}")
            post_text, hashtags = self._generate_f1_101_post(topic)
            
            posts.append({
                "event_title": topic['title'],
                "post_text": post_text,
                "hashtags": hashtags,
                "content": f"{post_text}\n\n{hashtags}",
                "technical": False,
                "educational": True,
                "topic_category": topic['category']
            })
        
        # Save the generated posts
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        posts_path = os.path.join(self.save_dir, f'f1_101_posts_{timestamp}.json')
        with open(posts_path, 'w') as f:
            json.dump(posts, f, indent=2)
        
        # Also save as plain text for easy reading
        text_path = os.path.join(self.save_dir, f'f1_101_posts_{timestamp}.txt')
        with open(text_path, 'w') as f:
            for i, post in enumerate(posts):
                f.write(f"Post {i+1}: {post['event_title']}\n")
                f.write(f"{'-' * 50}\n")
                f.write(f"{post['post_text']}\n\n")
                f.write(f"{post['hashtags']}\n\n")
        
        logger.info(f"Generated {len(posts)} educational posts and saved to {posts_path} and {text_path}")
        return posts
    
    def _generate_f1_101_topics(self, num_topics=5):
        """
        Generate a list of educational F1 topics for new fans.
        
        Args:
            num_topics: Number of topics to generate
            
        Returns:
            List of topic dictionaries with title, description, and category
        """
        # Categories for F1 educational content
        f1_categories = [
            "Racing Rules and Flags", 
            "Car Components and Technology",
            "Race Weekend Format",
            "Scoring and Championship",
            "Team Roles and Pit Stops",
            "F1 History and Iconic Moments",
            "Track Types and Features",
            "Driving Techniques",
            "Safety Features",
            "Strategy Elements"
        ]
        
        prompt = f"""You are an F1 educator creating a curated list of educational topics to help new Formula 1 fans understand the basics of the sport.

For each topic, provide:
1. A clear, concise title that captures the specific aspect of F1 being explained
2. A brief description of what this topic covers and why it's important for new fans
3. The category it belongs to (from: {', '.join(f1_categories)})

Please generate exactly {num_topics} educational topics that cover a good range of F1 fundamentals. 
Make sure the topics are diverse and cover different aspects of F1 from the categories provided.
Each topic should be something that can be explained in a short social media post format.

Format your response as a JSON array with the following structure:
[
  {{
    "title": "Topic Title",
    "description": "Brief description of what this covers",
    "category": "Category from the provided list"
  }},
  ...
]
"""
        
        # Call OpenRouter API
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        data = {
            "model": config.TEXT_MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 800,
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
                
                # Parse the JSON content
                try:
                    # Clean the response by removing markdown code block markers
                    if content.startswith('```json'):
                        content = content[7:]  # Remove ```json
                    if content.endswith('```'):
                        content = content[:-3]  # Remove ```
                    content = content.strip()
                    
                    content_data = json.loads(content)
                    
                    # Check if the content is directly an array or if it's inside a property
                    if isinstance(content_data, list):
                        topics = content_data
                    else:
                        # Look for an array in any of the top-level properties
                        topics = []
                        for value in content_data.values():
                            if isinstance(value, list) and len(value) > 0:
                                topics = value
                                break
                        
                        if not topics:
                            # If we can't find an array, just use the whole response
                            topics = [content_data]
                    
                    # Limit to the requested number of topics
                    return topics[:num_topics]
                
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON from LLM response: {str(e)}")
                    logger.error(f"Response content: {content}")
                    return []
            else:
                logger.error(f"Error from OpenRouter API: {response.status_code}, {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Exception when calling OpenRouter API: {str(e)}")
            return []
    
    def _generate_f1_101_post(self, topic):
        """
        Generate an educational post for a specific F1 topic.
        
        Args:
            topic: Topic dictionary with title, description, and category
            
        Returns:
            Tuple of (post_text, hashtags)
        """
        if not self.api_key:
            logger.error("OpenRouter API key not provided")
            return "API key required to generate educational content.", "#F1Basics"
        
        # Create the prompt for the LLM
        prompt = f"""You are an F1 educator creating a short, engaging educational post to help new Formula 1 fans understand an important concept.

The educational content should:
- Start with a simple, clear explanation that assumes no prior F1 knowledge
- Use conversational, friendly language appropriate for social media
- Focus on one specific concept without going into too many technical details
- Include a practical example or comparison to something everyday people understand
- Use present tense and active voice for clarity
- Add a memorable analogy or visualization to help the concept stick
- Keep to 2-3 sentences (50-70 words) for perfect social media delivery
- Include appropriate hashtags at the end, separated by a blank line
- When using numbers and measurements, spell them out fully for spoken delivery
  (e.g., "320 kilometers per hour" not "320 kmh", "2.4 seconds" not "2.4 s")

TOPIC DETAILS:
Title: {topic.get('title', 'Unknown topic')}
Description: {topic.get('description', 'No description available')}
Category: {topic.get('category', 'General F1 Knowledge')}

IMPORTANT: You MUST provide both educational text AND hashtags. Do not leave either section empty.
The educational text should be clear, simple, and engaging for new F1 fans.
The hashtags should include #F1Basics or #F1101 along with other relevant tags.

Structure your response EXACTLY as follows:
[Your educational text here]

[Your hashtags here]

Do not include any other text or explanations."""
        
        logger.info(f"Sending request to OpenRouter to generate educational post about: {topic.get('title', 'Unknown topic')}")
        
        # Call OpenRouter API
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        data = {
            "model": config.TEXT_MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        post_text = ""
        hashtags = ""
        
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data
            )
            
            if response.status_code == 200:
                result = response.json()
                full_text = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                # Split the response into main text and hashtags
                parts = full_text.strip().split("\n\n")
                if len(parts) >= 2:
                    post_text = self._clean_text(parts[0].strip())
                    hashtags = self._clean_text(parts[-1].strip())
                else:
                    # If there's no clear split, try to extract hashtags from the text
                    import re
                    post_text = self._clean_text(full_text.strip())
                    hashtags_matches = re.findall(r'#\w+', post_text)
                    if hashtags_matches:
                        # Remove hashtags from main text if they're at the end
                        clean_text = re.sub(r'(#\w+\s*)+$', '', post_text).strip()
                        if clean_text:  # Only use clean text if it's not empty
                            post_text = clean_text
                        hashtags = ' '.join(hashtags_matches)
                    else:
                        # If no hashtags found, add default ones
                        hashtags = f"#F1Basics #F1101 #{topic.get('category', 'F1').replace(' ', '')}"
            else:
                logger.error(f"Error from OpenRouter API: {response.status_code}, {response.text}")
                post_text = f"Failed to generate educational content about {topic.get('title', 'Unknown topic')}"
                hashtags = "#F1Basics #F1101"
                
        except Exception as e:
            logger.error(f"Exception when calling OpenRouter API: {str(e)}")
            post_text = f"Error generating educational content: {str(e)}"
            hashtags = "#F1Basics #F1101"
        
        # If we still don't have proper content, create a fallback message
        if not post_text:
            logger.warning(f"Creating fallback content for: {topic.get('title', 'Unknown topic')}")
            post_text = f"F1 basics: {topic.get('title', 'Unknown topic')} is an essential concept for new fans to understand. This aspect of Formula 1 helps make sense of race strategy and team decisions. Stay tuned for more F1 educational content to enhance your viewing experience!"
            hashtags = f"#F1Basics #F1101 #{topic.get('category', 'F1').replace(' ', '')}"
        
        # Format numbers and units for voiceover readability
        post_text = self._format_numbers_and_units(post_text)
        
        return post_text.strip(), hashtags.strip()

if __name__ == "__main__":
    # Simple test when run directly
    from paddock_pulse.f1_data_fetcher import F1DataFetcher
    from paddock_pulse.event_analyzer import F1EventAnalyzer
    
    # 1. Load F1 data
    fetcher = F1DataFetcher()
    data = fetcher.load_data()
    
    if not data:
        print("No F1 data available. Run f1_data_fetcher.py first to fetch data.")
    else:
        # 2. Analyze events
        analyzer = F1EventAnalyzer()
        events = analyzer.analyze_f1_data(data)
        
        if events:
            # 3. Generate posts
            generator = F1PostGenerator()
            posts = generator.generate_posts_from_events(events)
            print(f"Generated {len(posts)} posts") 