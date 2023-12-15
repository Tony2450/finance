import { TickerSymbols } from './tickerSymbols.js';

// Create a function to search over the ticker array
function searchTicker(str) {
    // Filter the ticker array based on the input string
    str = str.toLowerCase();
    const results = TickerSymbols.filter((item) => item.symbol.toLowerCase().includes(str) || item.name.toLowerCase().includes(str));

    let maxResults = 10;

    // If the results are greater than 10, return the first 10 results
    if (results.length > maxResults) {
        console.log(results.slice(0, maxResults))
        return results.slice(0, maxResults);
    }

    // Return the search results
    console.log(results)
    return results;
}


document.getElementById("search").addEventListener("input", e => {
    // Get the search value
    const searchValue = e.target.value;

    // Search the ticker array
    const results = searchTicker(searchValue);

    // Clear the results container
    document.getElementById("symbols").innerHTML = "";

    // Loop over the results and add them to the results container
    results.forEach((item) => {
        const div = document.createElement("option");
        div.setAttribute("value", item.symbol);
        div.innerHTML = item.name;
        document.getElementById("symbols").appendChild(div);
    })
})
