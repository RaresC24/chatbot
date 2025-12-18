const fs = require('fs');
const https = require('https');

// Configuration
const SERVICE_ID = "service_68xgedh";
const TEMPLATE_ID = "template_u1hvzzd";
const PUBLIC_KEY = "mgWI0Qdo5rJtWHBrz";
// Private key must be provided via environment variable for server-side sending
const PRIVATE_KEY = process.env.EMAILJS_PRIVATE_KEY;
const RECIPIENT_EMAIL = "claudiu.cotfas@gmail.com";

if (!PRIVATE_KEY) {
    console.error("Error: EMAILJS_PRIVATE_KEY env variable is missing.");
    process.exit(1);
}

// Read the log file
const logFile = 'conversations.csv';
let logContent = "";

try {
    if (fs.existsSync(logFile)) {
        logContent = fs.readFileSync(logFile, 'utf8');
    } else {
        console.log("No conversations.csv found. Skipping email.");
        process.exit(0);
    }
} catch (err) {
    console.error("Error reading log file:", err);
    process.exit(1);
}

if (!logContent.trim()) {
    console.log("Log file is empty. Skipping email.");
    process.exit(0);
}

// Prepare EmailJS payload
// We use the existing template parameters. We'll stuff the CSV into the 'message' field.
const messageBody = "Daily Conversation Log (" + new Date().toISOString().split('T')[0] + "):\n\n" + logContent;

const templateParams = {
    to_email: RECIPIENT_EMAIL,
    from_name: "Chatbot Daily Log",
    from_email: "noreply@chatbot.com",
    phone: "N/A",
    company: "System Log",
    message: messageBody
};

const data = JSON.stringify({
    service_id: SERVICE_ID,
    template_id: TEMPLATE_ID,
    user_id: PUBLIC_KEY,
    accessToken: PRIVATE_KEY,
    template_params: templateParams
});

// Send request
const options = {
    hostname: 'api.emailjs.com',
    path: '/api/v1.0/email/send',
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(data)
    }
};

const req = https.request(options, (res) => {
    let responseBody = '';

    res.on('data', (chunk) => {
        responseBody += chunk;
    });

    res.on('end', () => {
        if (res.statusCode === 200 || res.statusCode === 201) {
            console.log('Email sent successfully!');
        } else {
            console.error(`Failed to send email. Status: ${res.statusCode}`);
            console.error('Response:', responseBody);
            process.exit(1);
        }
    });
});

req.on('error', (error) => {
    console.error('Error making request:', error);
    process.exit(1);
});

req.write(data);
req.end();
