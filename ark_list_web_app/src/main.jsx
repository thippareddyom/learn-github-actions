import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import "./App.css";
import { SITE_TITLE, SITE_DESCRIPTION } from "./config";

const root = document.getElementById("root");

if (root) {
  if (SITE_TITLE) document.title = SITE_TITLE;
  if (SITE_DESCRIPTION) {
    let meta = document.querySelector('meta[name="description"]');
    if (!meta) {
      meta = document.createElement("meta");
      meta.name = "description";
      document.head.appendChild(meta);
    }
    meta.content = SITE_DESCRIPTION;
  }

  ReactDOM.createRoot(root).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}
