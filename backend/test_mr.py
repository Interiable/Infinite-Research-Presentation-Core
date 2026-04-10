import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.utils.media_researcher import MediaResearcher
mr = MediaResearcher()
print('Fetching transcript...')
res = mr.get_transcript('fZoAU6vM7o4')
print('Result length:', len(res))
if len(res) > 0:
    print('Preview:', res[:100])
else:
    print('Empty transcript returned!')
