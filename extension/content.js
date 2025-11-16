// content.js

// Map to store references to the actual DOM image elements using their unique ID.
// This is crucial for replacing the image later after translation.
const imageReferenceMap = {};

async function convertImageToBase64(src) {
    const response = await fetch(src);
    const blob = await response.blob();

    return new Promise((resolve) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result);
        reader.readAsDataURL(blob);
    });
}

async function collectImageData() {
    const imgElements = document.querySelectorAll("img");
    const imageDataArray = {};

    let results = [];

    for (let i = 0; i < imgElements.length; i++) {
        const img = imgElements[i];

        if (img.naturalWidth <= 50 || img.naturalHeight <= 50) continue;

        const id = `img-${i}`;
        imageReferenceMap[id] = img;

        try {
            const base64 = await convertImageToBase64(img.src);
            results.push({ id, data: base64 });
        } catch (err) {
            console.error("Error converting image:", img.src, err);
        }
    }

    chrome.runtime.sendMessage({
        action: "IMAGES_FOUND",
        images: results
    });
}

/**
 * Replaces the original image elements with the translated Base64 data.
 * @param {Array} translatedImages - Array of objects with { id, translatedData }.
 */
function replaceImages(translatedImages) {
    console.log(`Received ${translatedImages.length} translated images. Replacing...`);

    translatedImages.forEach(item => {
        const { id, translatedData } = item;
        const imgElement = imageReferenceMap[id];

        // Check if the DOM element reference exists and we have data to replace it with
        if (imgElement && translatedData) {
            // Replace the image source with the new Base64 data URL
            imgElement.src = translatedData;
        }
    });
}


// --- Message Listeners ---

// Listen for messages from the background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "START_TRANSLATION") {
        collectImageData();
        // Since we are sending an asynchronous message back via sendMessage,
        // we'll explicitly return true if we plan to use sendResponse later (though not used here, it's safer).
    } else if (request.action === "REPLACE_IMAGES") {
        // Handle the incoming translated image data from the background script
        replaceImages(request.translatedImages);
    }
});