const progress = document.querySelector("#startup-progress");
const fileInput = document.querySelector("#patient-file");
const status = document.querySelector("#status");

const startInput = document.querySelector("#start");
const endInput = document.querySelector("#end");
const analyseButton = document.querySelector("#analyse");
const results = document.querySelector("#results");
const removecauseInput = document.querySelector("#remove-cause")

let ready = false;
let busy = false;

// Enable analysis only after startup finishes and a file is selected with no request in progress.
function updateAnalyseButton() {
    analyseButton.disabled = !ready || busy || fileInput.files.length === 0;
}

// Show the selected filename and refresh analysis availability after file selection.
fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];
    status.textContent = file
        ? `Selected: ${file.name}`
        : "No file selected.";
    updateAnalyseButton()
});

const worker = new Worker("./worker.js");

// Reflect worker startup, results and errors in the progress and status controls.
worker.addEventListener("message", (event) => {
    if (event.data.type === "loading") {
        progress.hidden = false; progress.value = event.data.completed; status.textContent = event.data.message;
    } else if (event.data.type === "ready") {
        progress.value = 4; status.textContent = "Python, pandas and analysis package loaded."; ready = true; updateAnalyseButton()
    } else if (event.data.type === "error") {
        progress.hidden = true; status.textContent = `Startup failed: ${event.data.message}`;
    } else if (event.data.type === "result") {
        results.textContent = event.data.json; status.textContent = "Analysis complete."; busy = false; updateAnalyseButton()
    } else if (event.data.type === "analysis-error") {
        status.textContent = `Analysis failed: ${event.data.message}`; busy = false; updateAnalyseButton()
    }
});

// Read the selected CSV and send the requested analysis window and cause scenario to the worker.
analyseButton.addEventListener("click", async(event) => {
    if (!ready || busy || fileInput.files.length === 0){
         return;
    }
    busy = true; updateAnalyseButton(); results.textContent = "", status.textContent = "Analysing..."
    try{
        const csvText = await fileInput.files[0].text();
        worker.postMessage({
            type: "analyse", csvText: csvText, start: startInput.valueAsNumber, end: endInput.valueAsNumber,
            removeCause: removecauseInput.value.trim()
        });
    } catch (error) {status.textContent = error.message; busy = false; updateAnalyseButton()}
})