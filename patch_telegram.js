const fs = require('fs');
const file = '/usr/local/lib/node_modules/n8n/node_modules/.pnpm/n8n-nodes-base@file+packages+nodes-base_@aws-sdk+credential-providers@3.808.0_asn1.js@5_8da18263ca0574b0db58d4fefd8173ce/node_modules/n8n-nodes-base/dist/nodes/Telegram/GenericFunctions.js';

try {
    let content = fs.readFileSync(file, 'utf8');
    content = content.replace("additionalFields.parse_mode = 'Markdown';", "delete additionalFields.parse_mode;");
    fs.writeFileSync(file, content);
    console.log('Successfully patched GenericFunctions.js for plain text Telegram replies!');
} catch (err) {
    console.error('Could not patch Telegram node:', err.message);
}
