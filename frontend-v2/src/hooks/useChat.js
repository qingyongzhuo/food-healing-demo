import { useState, useRef, useCallback } from 'react';
import { streamChat } from '../lib/api';

export function useChat() {
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef(null);

  const sendMessage = useCallback((text, context = {}) => {
    const userMsg = { role: 'user', text, time: Date.now() };
    setMessages(prev => [...prev, userMsg]);

    const aiMsg = { role: 'ai', text: '', time: Date.now() };
    setMessages(prev => [...prev, aiMsg]);
    setIsStreaming(true);

    const controller = streamChat(
      {
        persona: 'nutritionist',
        messages: [{ role: 'user', content: text }],
        context,
      },
      {
        onDelta(delta) {
          setMessages(prev => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last.role === 'ai') {
              updated[updated.length - 1] = { ...last, text: last.text + delta };
            }
            return updated;
          });
        },
        onDone() {
          setIsStreaming(false);
        },
        onError(err) {
          setIsStreaming(false);
          setMessages(prev => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last.role === 'ai') {
              last.text = '抱歉，我暂时无法回复，请稍后再试。';
            }
            return updated;
          });
        },
      }
    );

    abortRef.current = controller;
    return controller;
  }, []);

  const clearMessages = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
    setIsStreaming(false);
  }, []);

  return { messages, isStreaming, sendMessage, clearMessages };
}