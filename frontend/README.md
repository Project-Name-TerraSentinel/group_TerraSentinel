# TerraPulse Frontend

A modern web application for soil degradation analysis and land restoration planning.

## Features

- **Farmer Interface**: Real-time soil health analysis with AI-powered recommendations
- **Planner Interface**: Regional degradation mapping and restoration prioritization
- **Live API Integration**: Connected to TerraPulse backend for ML predictions
- **Interactive Maps**: Leaflet-based mapping with degradation visualization
- **Responsive Design**: Works on desktop and mobile devices

## Quick Start

1. **Open the application**:
   ```bash
   # Serve the files using any web server
   # For example, using Python:
   python -m http.server 8080
   
   # Or using Node.js:
   npx serve .
   
   # Or using PHP:
   php -S localhost:8080
   ```

2. **Access the app**:
   Open `http://localhost:8080` in your browser

3. **Try the demo**:
   - Click "Try Farmer Demo" for the farmer interface
   - Click "Try Planner Demo" for the regional planning interface

## API Configuration

The frontend is configured to connect to your TerraPulse backend:

- **Backend URL**: `https://musical-fortnight-r4x5x66gvrqvcwqww-5000.app.github.dev`
- **API Key**: `dev-test-key`

To change the backend URL, edit `js/terra_api.js`:

```javascript
export const API_CONFIG = {
  baseURL: "YOUR_BACKEND_URL_HERE",
  apiKey: "your-api-key",
  timeoutMs: 30000
};
```

## File Structure

```
frontend/
├── index.html          # Main HTML file
├── styles.css          # CSS styles
├── js/
│   ├── main.js         # Main application logic
│   ├── terra_api.js    # Backend API client
│   ├── ui.js           # UI components
│   ├── map.js          # Map functionality
│   ├── utils.js        # Utility functions
│   ├── storage.js      # Local storage management
│   ├── location.js     # Geolocation utilities
│   └── auth.js         # Authentication (demo)
└── README.md           # This file
```

## Usage

### Farmer Interface

1. **Location Detection**: Automatically detects your location using GPS
2. **Soil Analysis**: Calls the backend API for degradation prediction
3. **AI Recommendations**: Shows personalized recommendations from Dify AI
4. **Actions**: Save, share, or report issues with predictions

### Planner Interface

1. **Regional Map**: View degradation patterns across multiple parcels
2. **Prioritization**: Adjust weights for degradation, area, and vulnerability
3. **Selection Tools**: Select high-priority parcels for restoration
4. **Export**: Download restoration plans as CSV files

## API Endpoints Used

- `POST /predict` - Basic soil degradation prediction
- `POST /enhanced-predict` - AI-enhanced prediction with recommendations
- `POST /ai` - Direct AI chat interface
- `GET /health/system` - Backend health check

## Browser Compatibility

- Chrome 80+
- Firefox 75+
- Safari 13+
- Edge 80+

## Dependencies

- **Leaflet**: Interactive maps
- **Tailwind CSS**: Styling framework
- **Native APIs**: Geolocation, Speech Synthesis, Fetch

## Development

To modify the frontend:

1. Edit the JavaScript files in the `js/` directory
2. Update styles in `styles.css`
3. Test with a local web server
4. Deploy to your web hosting service

## Deployment

1. **Static Hosting**: Upload files to any web server
2. **CDN**: Use services like Netlify, Vercel, or GitHub Pages
3. **Custom Domain**: Point your domain to the hosted files

## Troubleshooting

### API Connection Issues

1. Check that the backend is running
2. Verify the API URL in `js/terra_api.js`
3. Check browser console for error messages
4. Test the backend health endpoint directly

### Location Issues

1. Ensure HTTPS is used (required for geolocation)
2. Grant location permissions in browser
3. Use manual coordinate input as fallback

### Map Issues

1. Check internet connection (maps require external tiles)
2. Verify Leaflet CSS and JS are loaded
3. Check browser console for JavaScript errors

## Support

For issues with the frontend, check:
1. Browser developer console for errors
2. Network tab for failed API requests
3. Backend logs for server-side issues