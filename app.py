from flask import Flask, jsonify
from generate_affirmation_video import generate_affirmations_and_caption, create_video, post_to_facebook, post_to_instagram
import os

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "running", "message": "Affirmation Posting Service"})

@app.route('/generate', methods=['POST'])
def generate_post():
    try:
        # Generate content
        theme, affirmations, caption = generate_affirmations_and_caption()
        
        # Create video
        video = create_video(affirmations)
        output_path = f"output/{theme}_{datetime.now().strftime('%Y-%m-%d')}.mp4"
        video.write_videofile(output_path, fps=30)
        
        # Post to social media
        facebook_success = post_to_facebook(
            output_path,
            caption,
            os.getenv('FACEBOOK_ACCESS_TOKEN'),
            os.getenv('FACEBOOK_PAGE_ID')
        )
        
        instagram_success = post_to_instagram(
            output_path,
            caption,
            os.getenv('FACEBOOK_ACCESS_TOKEN'),
            os.getenv('INSTAGRAM_ACCOUNT_ID')
        )
        
        return jsonify({
            "status": "success",
            "theme": theme,
            "affirmations": affirmations,
            "caption": caption,
            "facebook_posted": facebook_success,
            "instagram_posted": instagram_success
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port) 