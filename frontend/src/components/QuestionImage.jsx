import React, { useState, useEffect } from 'react';
import api from '../utils/api';

/**
 * Fetches and displays an image attached to an exam question.
 *
 * Uses the authenticated /api/modules/{moduleId}/images/{imageId}/file endpoint
 * (which requires a JWT token) by fetching as a Blob and creating an object URL.
 * Renders nothing if imageId or moduleId is missing, or if the fetch fails.
 */
function QuestionImage({ imageId, moduleId, alt = 'Question image' }) {
  const [src, setSrc] = useState(null);

  useEffect(() => {
    if (!imageId || !moduleId) return;

    let objectUrl = null;

    api
      .get(`/modules/${moduleId}/images/${imageId}/file`, { responseType: 'blob' })
      .then((res) => {
        objectUrl = URL.createObjectURL(res.data);
        setSrc(objectUrl);
      })
      .catch(() => {
        // Silently ignore — question is still usable without the image
      });

    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [imageId, moduleId]);

  if (!src) return null;

  return (
    <img
      src={src}
      alt={alt}
      className="mt-3 max-w-full rounded border border-gray-200"
      style={{ maxHeight: '300px', objectFit: 'contain' }}
    />
  );
}

export default QuestionImage;
