// background.js

// 1. Listen for the user clicking the extension icon
chrome.action.onClicked.addListener((tab) => {
    if (tab.id) {
        // 2. Send a message to the content script in the active tab to start collection
        chrome.tabs.sendMessage(tab.id, {
            action: "START_TRANSLATION"
        });
    }
});


chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "IMAGES_FOUND") {
        console.log(`Found ${request.images.length} images to process. Sending to local server.`);
        // Pass the sender's tabId so we know where to send the results back
        sendImagesToPythonServer(request.images, sender.tab.id);
    }
});

async function fetchImageAndConvertToBase64(url) {
    try {
        const response = await fetch(url);

        // Ensure the response is OK and is an image
        if (!response.ok || !response.headers.get('content-type').startsWith('image/')) {
            console.error(`Failed to fetch image or resource is not an image: ${url}`);
            return null;
        }

        // Get image bytes as a Blob
        const blob = await response.blob();

        // Convert Blob to Base64 Data URL (using FileReader)
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
    } catch (error) {
        console.error("Error fetching image URL:", url, error);
        return null;
    }
}

async function sendImagesToPythonServer(images, tabId) {
    if (!images.length) return;

    try {
        const response = await fetch('http://localhost:5000/process_images', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ images })
        });

        const translatedImages = await response.json();

        chrome.tabs.sendMessage(tabId, {
            action: "REPLACE_IMAGES",
            translatedImages
        });

    } catch (err) {
        console.error("Error communicating with server:", err);
    }
}
