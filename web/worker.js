async function initialise() {
    try {
        self.postMessage({type: "loading", message: "Loading Python...", completed: 0});

        const baseURL = "https://cdn.jsdelivr.net/pyodide/v0.27.7/full/";
        importScripts(`${baseURL}pyodide.js`);

        const pyodide = await loadPyodide({indexURL: baseURL});
        
        self.postMessage({type: "loading", message: "Loading Pandas...", completed: 1});
        await pyodide.loadPackage("pandas");

        self.postMessage({type: "loading", message: "Loading package installer...", completed: 2});
        await pyodide.loadPackage("micropip");

        const wheelURL = new URL("./packages/deaths_warrant-0.1.0-py3-none-any.whl", self.location.href).href;

        pyodide.globals.set("wheel_url", wheelURL);

        self.postMessage({type: "loading", message: "Installing analysis package and checking imports...", completed: 3});
        await pyodide.runPythonAsync(`
            import micropip
            print("Installing analysis wheel...", flush = True)
            await micropip.install(wheel_url, deps = False)
            print("Analysis wheel installed.", flush = True)

            from deaths_warrant.schema import validate
            print("Schema imported.", flush = True)

            from deaths_warrant.estimators import AalenJohansenEstimator
            print("Estimators imported.", flush = True)

            from deaths_warrant.years_lost import summarise_years
            print("Years summary imported.", flush = True)

            from deaths_warrant.what_if import remove_cause
            print("Cause removal imported.", flush = True)
        `);
        const response = await fetch ("./analysis.py");
        
        if (!response.ok) {
            throw new Error("Could not load the browser analysis code.")
        }

        await pyodide.runPythonAsync(await response.text());

        self.addEventListener("message", async(event) => {
            if (event.data.type === "analyse") {
                try {
                    pyodide.globals.set("browser_csv", event.data.csvText); pyodide.globals.set("browser_start", event.data.start);
                    pyodide.globals.set("browser_end", event.data.end); pyodide.globals.set("browser_remove_cause", event.data.removeCause)
                    const json = await pyodide.runPythonAsync(
                        "analyse_csv(browser_csv, browser_start, browser_end, browser_remove_cause)"
                    );
                    const report = JSON.parse(json);
                    if (report.ok === true) {
                        self.postMessage({type: "result", json: JSON.stringify(report.summary, null, 2)});                        
                    } else {
                        self.postMessage({type: "analysis-error", message: report.error});
                    }
                } catch (error) {self.postMessage({type: "analysis-error", message: error.message});}
                finally {
                    pyodide.globals.delete("browser_csv"); pyodide.globals.delete("browser_start");
                    pyodide.globals.delete("browser_end"); pyodide.globals.delete("browser_remove_cause");
                    console.log("CSV global remains:", await pyodide.runPythonAsync("'browser_csv' in globals()"));
                }
            }
        });
        self.postMessage({type: "ready"});
    } catch (error) {self.postMessage({type: "error", message: error.message});}
}

initialise()