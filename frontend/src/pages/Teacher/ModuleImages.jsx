import React, { useEffect, useMemo, useState } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import {
  AlertCircle,
  Image as ImageIcon,
  Loader2,
  RefreshCcw,
  Search,
  Eye,
  Download,
  Layers,
  X,
} from 'lucide-react';
import api from '../../utils/api';
import { toast } from 'react-hot-toast';
import { useAuth } from '../../context/AuthContext';

function SecureModuleImageThumb({ moduleId, imageId, alt }) {
  const [src, setSrc] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!moduleId || !imageId) {
      setSrc(null);
      setFailed(false);
      return;
    }

    let objectUrl = null;
    let isActive = true;

    setSrc(null);
    setFailed(false);

    api
      .get(`/modules/${moduleId}/images/${imageId}/file`, { responseType: 'blob' })
      .then((res) => {
        if (!isActive) return;
        objectUrl = URL.createObjectURL(res.data);
        setSrc(objectUrl);
      })
      .catch(() => {
        if (isActive) setFailed(true);
      });

    return () => {
      isActive = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [moduleId, imageId]);

  if (src) {
    return (
      <img
        src={src}
        alt={alt}
        className="w-full h-full object-contain"
        loading="lazy"
      />
    );
  }

  return (
    <div className="w-full h-full flex items-center justify-center px-3 text-center">
      {failed ? (
        <p className="text-xs text-amber-700">Image unavailable</p>
      ) : (
        <Loader2 className="h-5 w-5 text-amber-600 animate-spin" />
      )}
    </div>
  );
}

const ModuleImages = () => {
  const { currentUser } = useAuth();
  const [modules, setModules] = useState([]);
  const [filteredModules, setFilteredModules] = useState([]);
  const [selectedModuleId, setSelectedModuleId] = useState(null);
  const [images, setImages] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [isLoadingModules, setIsLoadingModules] = useState(true);
  const [isLoadingImages, setIsLoadingImages] = useState(false);
  const [error, setError] = useState(null);
  const [previewImage, setPreviewImage] = useState(null);

  useEffect(() => {
    loadModules();
  }, [currentUser?.user_id]);

  useEffect(() => {
    filterModules(searchTerm);
  }, [modules, searchTerm]);

  useEffect(() => {
    if (filteredModules.length && !selectedModuleId) {
      setSelectedModuleId(filteredModules[0].module_id);
    }
  }, [filteredModules, selectedModuleId]);

  useEffect(() => {
    if (selectedModuleId) {
      loadImages(selectedModuleId);
    } else {
      setImages([]);
    }
  }, [selectedModuleId]);

  useEffect(() => {
    if (!previewImage) return undefined;
    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        setPreviewImage(null);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [previewImage]);

  useEffect(() => {
    return () => {
      if (previewImage?.url) {
        URL.revokeObjectURL(previewImage.url);
      }
    };
  }, [previewImage]);

  const loadModules = async () => {
    if (!currentUser?.user_id) return;

    setIsLoadingModules(true);
    setError(null);
    try {
      const res = await api.get(`/modules/teacher/${currentUser.user_id}`);
      if (res.data?.success) {
        const list = res.data.modules || [];
        setModules(list);
        setFilteredModules(list);
      } else {
        throw new Error(res.data?.message || 'Failed to load modules');
      }
    } catch (err) {
      const msg = err.response?.data?.message || err.message || 'Failed to load modules';
      setError(msg);
      toast.error(msg);
    } finally {
      setIsLoadingModules(false);
    }
  };

  const loadImages = async (moduleId) => {
    setIsLoadingImages(true);
    setError(null);
    try {
      const res = await api.get(`/modules/${moduleId}/images`);
      if (res.data?.success) {
        setImages(res.data.images || []);
      } else {
        throw new Error(res.data?.message || 'Failed to load images');
      }
    } catch (err) {
      const msg = err.response?.data?.message || err.message || 'Failed to load images';
      setError(msg);
      toast.error(msg);
      setImages([]);
    } finally {
      setIsLoadingImages(false);
    }
  };

  const filterModules = (term) => {
    if (!term) {
      setFilteredModules(modules);
      return;
    }
    const lowered = term.toLowerCase();
    setFilteredModules(
      modules.filter(
        (m) =>
          m.title?.toLowerCase().includes(lowered) ||
          m.subject_name?.toLowerCase().includes(lowered)
      )
    );
  };

  const selectedModule = useMemo(
    () => modules.find((m) => m.module_id === selectedModuleId),
    [modules, selectedModuleId]
  );

  const fetchImageBlob = async (moduleId, imageId) => {
    const res = await api.get(`/modules/${moduleId}/images/${imageId}/file`, {
      responseType: 'blob',
    });
    return res.data;
  };

  const getExtFromMime = (mimeType = '') => {
    const map = {
      'image/jpeg': 'jpg',
      'image/jpg': 'jpg',
      'image/png': 'png',
      'image/webp': 'webp',
      'image/gif': 'gif',
      'image/bmp': 'bmp',
      'image/tiff': 'tiff',
      'image/svg+xml': 'svg',
    };
    return map[mimeType.toLowerCase()] || 'img';
  };

  const handleOpenImage = async (img) => {
    if (!selectedModuleId) return;
    try {
      const blob = await fetchImageBlob(selectedModuleId, img.image_id);
      const blobUrl = URL.createObjectURL(blob);
      setPreviewImage((previous) => {
        if (previous?.url) {
          URL.revokeObjectURL(previous.url);
        }
        return {
          url: blobUrl,
          imageId: img.image_id,
          imageNumber: (img.image_index ?? 0) + 1,
        };
      });
    } catch (err) {
      toast.error('Failed to open image');
    }
  };

  const closePreview = () => {
    setPreviewImage((previous) => {
      if (previous?.url) {
        URL.revokeObjectURL(previous.url);
      }
      return null;
    });
  };

  const handleDownloadImage = async (img) => {
    if (!selectedModuleId) return;
    try {
      const blob = await fetchImageBlob(selectedModuleId, img.image_id);
      const ext = getExtFromMime(blob.type);
      const name = `module_${selectedModuleId}_image_${(img.image_index ?? 0) + 1}_${img.image_id}.${ext}`;
      const blobUrl = URL.createObjectURL(blob);

      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = name;
      document.body.appendChild(link);
      link.click();
      link.remove();

      setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
    } catch (err) {
      toast.error('Failed to download image');
    }
  };

  if (isLoadingModules) {
    return (
      <div className="p-6 bg-gradient-to-b from-amber-50/20 to-white rounded-xl">
        <div className="flex items-center justify-center h-64 rounded-xl border border-amber-200 bg-white">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-amber-500 mx-auto mb-4"></div>
            <p className="text-amber-800">Loading module images...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error && !selectedModuleId && !modules.length) {
    return (
      <div className="p-6">
        <Card className="border border-amber-200 rounded-xl">
          <CardContent className="pt-6">
            <div className="text-center py-12">
              <div className="mx-auto w-16 h-16 bg-red-50 rounded-full flex items-center justify-center mb-4">
                <AlertCircle className="h-8 w-8 text-red-500" />
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">Unable to load images</h3>
              <p className="text-gray-500 mb-4">{error}</p>
              <Button onClick={loadModules}>Try Again</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 bg-gradient-to-b from-amber-50/20 to-white rounded-xl p-1">
      <div className="rounded-xl border border-amber-200 bg-white shadow-sm p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-amber-900">Module Images</h1>
            <p className="text-sm text-amber-800">
            Browse images extracted from your uploaded modules.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                loadModules();
                if (selectedModuleId) loadImages(selectedModuleId);
              }}
              className="flex items-center gap-2 border-amber-300 text-amber-900 hover:bg-amber-50"
            >
              <RefreshCcw className="h-4 w-4" />
              Refresh
            </Button>
            <Badge variant="secondary" className="text-sm flex items-center gap-1 border border-amber-300 bg-amber-50 text-amber-800">
              <Layers className="h-4 w-4" />
              {modules.length} modules
            </Badge>
          </div>
        </div>
      </div>

      <Card className="border border-amber-200 rounded-xl shadow-sm">
        <CardHeader className="pb-4">
          <CardTitle className="text-lg text-amber-900">Select Module</CardTitle>
          <CardDescription className="text-amber-800">
            Search your modules and view all extracted images.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="md:col-span-2">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-amber-500" />
                <Input
                  placeholder="Search modules by title or subject..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10 border-amber-200 focus-visible:ring-amber-500"
                />
              </div>
            </div>
            <div>
              <select
                className="w-full h-10 border border-amber-200 rounded-md px-3 py-2 bg-white text-amber-900 focus:outline-none focus:ring-2 focus:ring-amber-500"
                value={selectedModuleId || ''}
                onChange={(e) => setSelectedModuleId(Number(e.target.value) || null)}
              >
                {!selectedModuleId && <option value="">Select a module</option>}
                {filteredModules.map((m) => (
                  <option key={m.module_id} value={m.module_id}>
                    {m.title} {m.subject_name ? `- ${m.subject_name}` : ''}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {selectedModule && (
            <div className="flex flex-wrap items-center gap-3 text-sm text-amber-800">
              <Badge variant="outline" className="flex items-center gap-1 border-amber-300 bg-amber-50 text-amber-800">
                <ImageIcon className="h-4 w-4" />
                {images.length} images
              </Badge>
              <span>
                Subject: <strong>{selectedModule.subject_name || 'N/A'}</strong>
              </span>
              <span>
                File Type: <strong>{selectedModule.file_type || 'N/A'}</strong>
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="border border-amber-200 rounded-xl shadow-sm">
        <CardHeader className="pb-4">
          <CardTitle className="text-lg flex items-center gap-2 text-amber-900">
            <ImageIcon className="h-5 w-5 text-amber-600" />
            Extracted Images
          </CardTitle>
          <CardDescription className="text-amber-800">
            Thumbnails are loaded from the secured module image endpoint.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoadingImages ? (
            <div className="py-12 flex flex-col items-center justify-center gap-3">
              <Loader2 className="h-8 w-8 text-amber-600 animate-spin" />
              <p className="text-amber-800">Loading images...</p>
            </div>
          ) : !selectedModuleId ? (
            <div className="py-10 text-center text-amber-800">
              Select a module above to view its images.
            </div>
          ) : images.length === 0 ? (
            <div className="py-10 text-center text-amber-800">
              No images were extracted for this module.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {images.map((img) => (
                <div
                  key={img.image_id}
                  className="rounded-xl border border-amber-200 overflow-hidden bg-white shadow-sm hover:shadow-md transition-shadow"
                >
                  <div className="bg-amber-50 p-2 border-b border-amber-200">
                    <div className="text-xs text-amber-800 flex items-center justify-between">
                      <span>Image #{(img.image_index ?? 0) + 1}</span>
                      <span className="text-amber-700">ID: {img.image_id}</span>
                    </div>
                  </div>
                  <div
                    className="h-60 bg-amber-50/40 flex items-center justify-center overflow-hidden cursor-zoom-in"
                    onClick={() => handleOpenImage(img)}
                    title="Click to view larger image"
                  >
                    <SecureModuleImageThumb
                      moduleId={selectedModuleId}
                      imageId={img.image_id}
                      alt={`Module ${selectedModuleId} image ${img.image_id}`}
                    />
                  </div>
                  <div className="p-3 flex items-center justify-between">
                    <Button
                      variant="outline"
                      size="sm"
                      className="flex items-center gap-1 border-amber-300 text-amber-900 hover:bg-amber-50"
                      onClick={() => handleOpenImage(img)}
                    >
                      <Eye className="h-4 w-4" />
                      View
                    </Button>
                    <button
                      type="button"
                      onClick={() => handleDownloadImage(img)}
                      className="inline-flex items-center gap-1 text-sm text-amber-700 hover:text-amber-900 font-medium"
                    >
                      <Download className="h-4 w-4" />
                      Download
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {previewImage && (
        <div className="fixed inset-0 z-[130] flex items-center justify-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-black/70"
            onClick={closePreview}
            aria-label="Close image preview"
          />

          <div className="relative w-full max-w-[1400px] rounded-xl border border-amber-200 bg-white shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between border-b border-amber-200 px-4 py-3">
              <div>
                <h2 className="text-base font-semibold text-amber-900">Image Preview</h2>
                <p className="text-xs text-amber-700">
                  Image #{previewImage.imageNumber} (ID: {previewImage.imageId})
                </p>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="border-amber-300 text-amber-900 hover:bg-amber-50"
                onClick={closePreview}
              >
                <X className="h-4 w-4 mr-1" />
                Close
              </Button>
            </div>

            <div className="max-h-[80vh] overflow-auto bg-neutral-900 p-4 md:p-6">
              <div className="flex min-h-[50vh] items-center justify-center">
                <img
                  src={previewImage.url}
                  alt={`Module ${selectedModuleId} image ${previewImage.imageId}`}
                  className="h-auto max-w-none rounded-md border border-white/20 bg-white shadow-lg"
                  style={{ width: 'min(92vw, 1350px)' }}
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ModuleImages;
