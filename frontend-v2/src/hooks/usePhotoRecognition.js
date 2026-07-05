import { useState, useRef, useCallback, useEffect } from 'react';
import toast from 'react-hot-toast';
import { recognizeWithPolling } from '../lib/api';

export function usePhotoRecognition() {
  const [isRecognizing, setIsRecognizing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const abortRef = useRef(null);

  // 卸载时中断 in-flight 请求，避免 setState 已卸载组件
  useEffect(() => () => abortRef.current?.abort(), []);

  const startRecognize = useCallback(async (file) => {
    setIsRecognizing(true);
    setProgress(0);
    setResult(null);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const data = await recognizeWithPolling(file, {
        onProgress: setProgress,
        signal: controller.signal,
      });
      setProgress(100);
      // data 现在包含 ingredients, dish, pairing
      setResult(data);
      return data;
    } catch (err) {
      // 主动取消静默处理：靠 ApiError.code===0 && message==='已取消' 双重判断
      const isUserCancel = err?.code === 0 && err?.message === '已取消';
      if (!isUserCancel && err?.name !== 'AbortError') {
        setResult(null);
        toast.error(err?.message || '识别失败');
      }
      return null;
    } finally {
      setIsRecognizing(false);
      abortRef.current = null;
    }
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setIsRecognizing(false);
  }, []);

  const reset = useCallback(() => {
    setResult(null);
    setProgress(0);
  }, []);

  return { isRecognizing, progress, result, startRecognize, cancel, reset };
}
