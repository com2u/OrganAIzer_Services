// Load environment variables from .env file
require('dotenv').config();

const express = require('express');
const { google } = require('googleapis');

// Initialize Express app
const app = express();
const PORT = 3000;

// ============================================================
// ENVIRONMENT VARIABLE VALIDATION
// Validate required environment variables are set
// ============================================================
const requiredEnvVars = [
  'GOOGLE_CLIENT_ID',
  'GOOGLE_CLIENT_SECRET',
  'GOOGLE_REDIRECT_URI'
];

const missingVars = requiredEnvVars.filter(varName => !process.env[varName]);

if (missingVars.length > 0) {
  console.error('❌ ERROR: Missing required environment variables:');
  missingVars.forEach(varName => {
    console.error(`   - ${varName}`);
  });
  console.error('\n📝 Please create a .env file with the required variables.');
  console.error('   You can copy .env.example and fill in your values:\n');
  console.error('   copy .env.example .env\n');
  process.exit(1);
}

// In-memory token storage (for testing purposes only)
let tokens = null;

// Configure OAuth2 client using environment variables
// This client will be used for all Google API interactions
const oauth2Client = new google.auth.OAuth2(
  process.env.GOOGLE_CLIENT_ID,
  process.env.GOOGLE_CLIENT_SECRET,
  process.env.GOOGLE_REDIRECT_URI
);

// Define OAuth scopes - what permissions we're requesting
// Gmail: read emails and send emails
// Calendar: manage calendar events
const SCOPES = [
  'https://www.googleapis.com/auth/gmail.readonly',
  'https://www.googleapis.com/auth/gmail.send',
  'https://www.googleapis.com/auth/calendar.events'
];

// ============================================================
// ROUTE: GET /
// Home page with a link to initiate Google OAuth
// ============================================================
app.get('/', (req, res) => {
  res.send(`
    <!DOCTYPE html>
    <html>
      <head>
        <title>Google OAuth Test</title>
        <style>
          body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            text-align: center;
          }
          .button {
            display: inline-block;
            padding: 15px 30px;
            background-color: #4285f4;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-size: 18px;
            margin: 10px;
          }
          .button:hover {
            background-color: #357ae8;
          }
          .test-button {
            background-color: #34a853;
          }
          .test-button:hover {
            background-color: #2d9148;
          }
          .section {
            margin: 30px 0;
            padding: 20px;
            border: 1px solid #ddd;
            border-radius: 5px;
          }
          .status {
            padding: 10px;
            margin: 10px 0;
            border-radius: 5px;
            background-color: ${tokens ? '#d4edda' : '#fff3cd'};
            color: ${tokens ? '#155724' : '#856404'};
            border: 1px solid ${tokens ? '#c3e6cb' : '#ffeeba'};
          }
        </style>
      </head>
      <body>
        <h1>Google OAuth 2.0 Test Server</h1>
        
        <div class="status">
          <strong>Status:</strong> ${tokens ? '✓ Connected to Google' : '✗ Not connected'}
        </div>
        
        <div class="section">
          <h2>Step 1: Connect to Google</h2>
          <a href="/auth/google" class="button">Connect Google Account</a>
        </div>
        
        ${tokens ? `
          <div class="section">
            <h2>Step 2: Test APIs</h2>
            <a href="/test/gmail" class="button test-button">Test Gmail API</a>
            <a href="/test/calendar" class="button test-button">Test Calendar API</a>
          </div>
        ` : ''}
        
        <div class="section">
          <h3>Instructions</h3>
          <ol style="text-align: left;">
            <li>Click "Connect Google Account" to start OAuth flow</li>
            <li>Sign in with your Google account</li>
            <li>Grant the requested permissions</li>
            <li>You'll be redirected back and the test buttons will appear</li>
            <li>Click test buttons to verify Gmail and Calendar API access</li>
          </ol>
        </div>
      </body>
    </html>
  `);
});

// ============================================================
// ROUTE: GET /auth/google
// Initiates the Google OAuth flow by redirecting to Google's consent page
// ============================================================
app.get('/auth/google', (req, res) => {
  // Generate the OAuth URL with required parameters
  // access_type: 'offline' - requests a refresh token for long-term access
  // prompt: 'consent' - forces the consent screen to appear every time
  const authUrl = oauth2Client.generateAuthUrl({
    access_type: 'offline',
    prompt: 'consent',
    scope: SCOPES,
  });

  console.log('Redirecting to Google OAuth URL:', authUrl);
  
  // Redirect the user's browser to Google's OAuth consent page
  res.redirect(authUrl);
});

// ============================================================
// ROUTE: GET /oauth2callback
// Google redirects here after user grants/denies permissions
// This route exchanges the authorization code for access tokens
// ============================================================
app.get('/oauth2callback', async (req, res) => {
  // Extract the authorization code from the query parameters
  const code = req.query.code;

  if (!code) {
    return res.status(400).send('Error: No authorization code received');
  }

  try {
    // Exchange the authorization code for access and refresh tokens
    const { tokens: newTokens } = await oauth2Client.getToken(code);
    
    // DO NOT log tokens - security risk
    console.log('✓ OAuth tokens received successfully');
    
    // Store tokens in memory
    tokens = newTokens;
    
    // Set the credentials on the OAuth client
    // This allows all subsequent API calls to be authenticated
    oauth2Client.setCredentials(tokens);

    // Send success response (tokens NOT displayed for security)
    res.send(`
      <!DOCTYPE html>
      <html>
        <head>
          <title>OAuth Success</title>
          <style>
            body {
              font-family: Arial, sans-serif;
              max-width: 800px;
              margin: 50px auto;
              padding: 20px;
            }
            .success {
              padding: 20px;
              background-color: #d4edda;
              color: #155724;
              border: 1px solid #c3e6cb;
              border-radius: 5px;
              margin: 20px 0;
            }
            .button {
              display: inline-block;
              padding: 10px 20px;
              background-color: #4285f4;
              color: white;
              text-decoration: none;
              border-radius: 5px;
              margin-top: 20px;
            }
            .info {
              padding: 15px;
              background-color: #f8f9fa;
              border-left: 4px solid #4285f4;
              margin: 20px 0;
            }
          </style>
        </head>
        <body>
          <h1>✓ OAuth Successful!</h1>
          <div class="success">
            <p><strong>Successfully connected to Google!</strong></p>
            <p>Your access tokens have been securely stored in memory.</p>
            <p>You can now test the Gmail and Calendar APIs.</p>
          </div>
          
          <div class="info">
            <p><strong>ℹ️ Security Note:</strong> Tokens are stored in memory and not displayed for security reasons.</p>
            <p>The tokens will be automatically used for API calls and will be lost when the server restarts.</p>
          </div>
          
          <a href="/" class="button">← Back to Home</a>
        </body>
      </html>
    `);
  } catch (error) {
    console.error('Error exchanging code for tokens:', error);
    res.status(500).send(`Error getting tokens: ${error.message}`);
  }
});

// ============================================================
// ROUTE: GET /test/gmail
// Tests Gmail API by fetching the 5 most recent emails
// ============================================================
app.get('/test/gmail', async (req, res) => {
  // Check if we have valid tokens
  if (!tokens) {
    return res.status(401).send('Not authenticated. Please visit <a href="/">home</a> and connect your Google account.');
  }

  try {
    // Create Gmail API client instance
    const gmail = google.gmail({ version: 'v1', auth: oauth2Client });

    // Fetch list of messages from the user's mailbox
    // userId: 'me' means the authenticated user
    // maxResults: 5 limits the response to 5 most recent emails
    const response = await gmail.users.messages.list({
      userId: 'me',
      maxResults: 5,
    });

    const messages = response.data.messages || [];

    // If no messages found, return early
    if (messages.length === 0) {
      return res.send('<h1>No messages found</h1><a href="/">← Back to Home</a>');
    }

    // Fetch full details for each message
    // This includes subject, sender, snippet, etc.
    const messageDetails = await Promise.all(
      messages.map(async (message) => {
        const msg = await gmail.users.messages.get({
          userId: 'me',
          id: message.id,
        });
        
        // Extract useful headers
        const headers = msg.data.payload.headers;
        const subject = headers.find(h => h.name === 'Subject')?.value || 'No Subject';
        const from = headers.find(h => h.name === 'From')?.value || 'Unknown';
        const date = headers.find(h => h.name === 'Date')?.value || 'Unknown';
        
        return {
          id: message.id,
          subject,
          from,
          date,
          snippet: msg.data.snippet,
        };
      })
    );

    // Display the results in a formatted HTML page
    res.send(`
      <!DOCTYPE html>
      <html>
        <head>
          <title>Gmail Test Results</title>
          <style>
            body {
              font-family: Arial, sans-serif;
              max-width: 900px;
              margin: 50px auto;
              padding: 20px;
            }
            .email {
              border: 1px solid #ddd;
              padding: 15px;
              margin: 10px 0;
              border-radius: 5px;
              background-color: #f9f9f9;
            }
            .email h3 {
              margin-top: 0;
              color: #333;
            }
            .meta {
              color: #666;
              font-size: 14px;
              margin: 5px 0;
            }
            .snippet {
              color: #555;
              font-style: italic;
              margin-top: 10px;
            }
            .button {
              display: inline-block;
              padding: 10px 20px;
              background-color: #4285f4;
              color: white;
              text-decoration: none;
              border-radius: 5px;
              margin-top: 20px;
            }
            pre {
              background-color: #f5f5f5;
              padding: 15px;
              border-radius: 5px;
              overflow-x: auto;
              font-size: 12px;
            }
          </style>
        </head>
        <body>
          <h1>✓ Gmail API Test Successful</h1>
          <p>Fetched ${messageDetails.length} most recent emails:</p>
          
          ${messageDetails.map(msg => `
            <div class="email">
              <h3>${msg.subject}</h3>
              <div class="meta"><strong>From:</strong> ${msg.from}</div>
              <div class="meta"><strong>Date:</strong> ${msg.date}</div>
              <div class="meta"><strong>ID:</strong> ${msg.id}</div>
              <div class="snippet">${msg.snippet}</div>
            </div>
          `).join('')}
          
          <h2>Raw JSON Response:</h2>
          <pre>${JSON.stringify(messageDetails, null, 2)}</pre>
          
          <a href="/" class="button">← Back to Home</a>
        </body>
      </html>
    `);
  } catch (error) {
    console.error('Gmail API Error:', error);
    res.status(500).send(`
      <h1>Gmail API Error</h1>
      <p>${error.message}</p>
      <pre>${JSON.stringify(error, null, 2)}</pre>
      <a href="/">← Back to Home</a>
    `);
  }
});

// ============================================================
// ROUTE: GET /test/calendar
// Tests Calendar API by fetching the next 5 upcoming events
// ============================================================
app.get('/test/calendar', async (req, res) => {
  // Check if we have valid tokens
  if (!tokens) {
    return res.status(401).send('Not authenticated. Please visit <a href="/">home</a> and connect your Google account.');
  }

  try {
    // Create Calendar API client instance
    const calendar = google.calendar({ version: 'v3', auth: oauth2Client });

    // Fetch upcoming events from the user's primary calendar
    // calendarId: 'primary' means the user's main calendar
    // timeMin: current time (only get future events)
    // maxResults: 5 limits to 5 events
    // singleEvents: true expands recurring events into individual instances
    // orderBy: 'startTime' sorts events by start time
    const response = await calendar.events.list({
      calendarId: 'primary',
      timeMin: new Date().toISOString(),
      maxResults: 5,
      singleEvents: true,
      orderBy: 'startTime',
    });

    const events = response.data.items || [];

    // If no events found, return early
    if (events.length === 0) {
      return res.send(`
        <!DOCTYPE html>
        <html>
          <head><title>Calendar Test</title></head>
          <body>
            <h1>No upcoming events found</h1>
            <a href="/">← Back to Home</a>
          </body>
        </html>
      `);
    }

    // Format events for display
    const formattedEvents = events.map(event => ({
      id: event.id,
      summary: event.summary || 'No Title',
      start: event.start.dateTime || event.start.date,
      end: event.end.dateTime || event.end.date,
      location: event.location || 'No location',
      description: event.description || 'No description',
      htmlLink: event.htmlLink,
    }));

    // Display the results in a formatted HTML page
    res.send(`
      <!DOCTYPE html>
      <html>
        <head>
          <title>Calendar Test Results</title>
          <style>
            body {
              font-family: Arial, sans-serif;
              max-width: 900px;
              margin: 50px auto;
              padding: 20px;
            }
            .event {
              border: 1px solid #ddd;
              padding: 15px;
              margin: 10px 0;
              border-radius: 5px;
              background-color: #f9f9f9;
            }
            .event h3 {
              margin-top: 0;
              color: #333;
            }
            .meta {
              color: #666;
              font-size: 14px;
              margin: 5px 0;
            }
            .button {
              display: inline-block;
              padding: 10px 20px;
              background-color: #4285f4;
              color: white;
              text-decoration: none;
              border-radius: 5px;
              margin-top: 20px;
            }
            pre {
              background-color: #f5f5f5;
              padding: 15px;
              border-radius: 5px;
              overflow-x: auto;
              font-size: 12px;
            }
            a.event-link {
              color: #4285f4;
              text-decoration: none;
            }
          </style>
        </head>
        <body>
          <h1>✓ Calendar API Test Successful</h1>
          <p>Fetched ${formattedEvents.length} upcoming events:</p>
          
          ${formattedEvents.map(event => `
            <div class="event">
              <h3>${event.summary}</h3>
              <div class="meta"><strong>Start:</strong> ${new Date(event.start).toLocaleString()}</div>
              <div class="meta"><strong>End:</strong> ${new Date(event.end).toLocaleString()}</div>
              <div class="meta"><strong>Location:</strong> ${event.location}</div>
              <div class="meta"><strong>Description:</strong> ${event.description}</div>
              <div class="meta"><strong>ID:</strong> ${event.id}</div>
              <div class="meta"><a href="${event.htmlLink}" target="_blank" class="event-link">View in Google Calendar</a></div>
            </div>
          `).join('')}
          
          <h2>Raw JSON Response:</h2>
          <pre>${JSON.stringify(formattedEvents, null, 2)}</pre>
          
          <a href="/" class="button">← Back to Home</a>
        </body>
      </html>
    `);
  } catch (error) {
    console.error('Calendar API Error:', error);
    res.status(500).send(`
      <h1>Calendar API Error</h1>
      <p>${error.message}</p>
      <pre>${JSON.stringify(error, null, 2)}</pre>
      <a href="/">← Back to Home</a>
    `);
  }
});

// Start the Express server
app.listen(PORT, () => {
  console.log('='.repeat(60));
  console.log('Google OAuth 2.0 Test Server');
  console.log('='.repeat(60));
  console.log(`Server running at: http://localhost:${PORT}`);
  console.log('');
  console.log('Environment variables loaded:');
  console.log(`  GOOGLE_CLIENT_ID: ${process.env.GOOGLE_CLIENT_ID ? '✓ Set' : '✗ Missing'}`);
  console.log(`  GOOGLE_CLIENT_SECRET: ${process.env.GOOGLE_CLIENT_SECRET ? '✓ Set' : '✗ Missing'}`);
  console.log(`  GOOGLE_REDIRECT_URI: ${process.env.GOOGLE_REDIRECT_URI || '✗ Missing'}`);
  console.log('');
  console.log('OAuth Scopes:');
  SCOPES.forEach(scope => console.log(`  - ${scope}`));
  console.log('');
  console.log('To get started:');
  console.log(`  1. Open http://localhost:${PORT} in your browser`);
  console.log('  2. Click "Connect Google Account"');
  console.log('  3. Grant permissions');
  console.log('  4. Test the Gmail and Calendar APIs');
  console.log('='.repeat(60));
});
