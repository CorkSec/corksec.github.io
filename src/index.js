import "./reset.css";
import "./style.css";

import axe from "axe-core";

axe
  .run()
  .then((results) => {
    if (results.violations.length) {
      console.log(results.violations);
      throw new Error("Accessibility issues found");
    }
  })
  .catch((err) => {
    console.error("Something bad happened:", err.message);
  });
