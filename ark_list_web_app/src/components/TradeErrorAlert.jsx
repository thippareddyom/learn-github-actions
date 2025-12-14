import React from "react";

const TradeErrorAlert = ({ message, onDismiss }) =>
  !message ? null : (
    <div className="status status--error" role="alert">
      {message}
      <button type="button" className="link-btn" onClick={onDismiss} style={{ marginLeft: "0.5rem" }}>
        Dismiss
      </button>
    </div>
  );

export default TradeErrorAlert;
