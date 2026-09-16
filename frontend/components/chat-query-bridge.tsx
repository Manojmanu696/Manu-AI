"use client";

import { useEffect } from "react";

const HANDOFF_KEY = "manu-ai-pending-query";
const AUTO_SUBMIT_KEY = "manu-ai-auto-submit";

function setReactControlledValue(element: HTMLInputElement | HTMLTextAreaElement, value: string) {
  const prototype = element instanceof HTMLTextAreaElement
    ? HTMLTextAreaElement.prototype
    : HTMLInputElement.prototype;
  const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");
  descriptor?.set?.call(element, value);
  element.dispatchEvent(new Event("input", { bubbles: true }));
  element.dispatchEvent(new Event("change", { bubbles: true }));
}

export default function ChatQueryBridge() {
  useEffect(() => {
    const captureHomeQuery = (event: Event) => {
      const form = event.target instanceof Element ? event.target.closest("form.ask-box") : null;
      if (!form) return;
      const field = form.querySelector("input") as HTMLInputElement | null;
      const query = field?.value.trim();
      if (!query) return;
      sessionStorage.setItem(HANDOFF_KEY, query);
      sessionStorage.setItem(AUTO_SUBMIT_KEY, "1");
    };

    const deliverQueryToAI = () => {
      const query = sessionStorage.getItem(HANDOFF_KEY);
      if (!query) return;

      const textarea = Array.from(document.querySelectorAll("textarea"))
        .find((node) => node.getAttribute("placeholder") === "Ask Manu AI anything…") as HTMLTextAreaElement | undefined;
      if (!textarea) return;

      if (textarea.value !== query) setReactControlledValue(textarea, query);
      textarea.focus();

      if (sessionStorage.getItem(AUTO_SUBMIT_KEY) === "1") {
        sessionStorage.removeItem(AUTO_SUBMIT_KEY);
        window.setTimeout(() => {
          const form = textarea.form;
          if (form) form.requestSubmit();
        }, 120);
      }
      sessionStorage.removeItem(HANDOFF_KEY);
    };

    document.addEventListener("submit", captureHomeQuery, true);
    const observer = new MutationObserver(deliverQueryToAI);
    observer.observe(document.body, { childList: true, subtree: true });
    deliverQueryToAI();

    return () => {
      document.removeEventListener("submit", captureHomeQuery, true);
      observer.disconnect();
    };
  }, []);

  return null;
}
