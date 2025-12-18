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
// Parse CSV locally (since we don't have npm modules)
// Handles "quoted string with newlines" basic CSV format
function parseCSV(text) {
    const records = [];
    let currentRecord = [];
    let currentField = "";
    let insideQuotes = false;

    // Iterate char by char to handle quotes correctly
    for (let i = 0; i < text.length; i++) {
        const char = text[i];
        const nextChar = text[i + 1];

        if (char === '"') {
            if (insideQuotes && nextChar === '"') {
                // Escaped quote ("") -> add one quote
                currentField += '"';
                i++; // Skip next quote
            } else {
                // Toggle state
                insideQuotes = !insideQuotes;
            }
        } else if (char === ',' && !insideQuotes) {
            // End of field
            currentRecord.push(currentField);
            currentField = "";
        } else if ((char === '\r' || char === '\n') && !insideQuotes) {
            // End of line/record (handle \r\n or \n)
            if (char === '\r' && nextChar === '\n') {
                i++; // Skip \n
            }
            // Only add if not empty (avoids trailing newlines)
            if (currentField || currentRecord.length > 0) {
                currentRecord.push(currentField);
                records.push(currentRecord);
                currentRecord = [];
                currentField = "";
            }
        } else {
            currentField += char;
        }
    }
    // Push last record if exists
    if (currentField || currentRecord.length > 0) {
        currentRecord.push(currentField);
        records.push(currentRecord);
    }
    return records;
}

const parsedLogs = parseCSV(logContent);
let formattedBody = "Daily Conversation Log (" + new Date().toISOString().split('T')[0] + "):\n\n";

// CSV Format: conversationId, timestamp, ip, country, languages, transcript
// Skip header row if present (simple heuristic: check if first col is "conversationId")
parsedLogs.forEach((row, index) => {
    if (row.length < 5) return; // Skip malformed rows
    if (index === 0 && row[0] === 'conversationId') return; // Skip header

    const [id, time, ip, country, langs, transcript] = row;

    formattedBody += "• Conversation ID: " + id + "\n";
    formattedBody += "   Date: " + time + "\n";
    formattedBody += "   IP: " + ip + " (" + country + ")\n";
    formattedBody += "   Languages: " + langs + "\n";
    formattedBody += "   Transcript:\n";
    formattedBody += "   " + (transcript ? transcript.replace(/\n/g, "\n   ") : "No content") + "\n";
    formattedBody += "\n--------------------------------------------------\n\n";
});

const messageBody = formattedBody;

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
