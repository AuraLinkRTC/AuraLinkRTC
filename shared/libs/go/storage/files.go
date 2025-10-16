package storage

import (
	"context"
	"fmt"
	"io"
	"path/filepath"
	"time"

	"github.com/google/uuid"
	storage_go "github.com/supabase-community/storage-go"
)

// Config holds storage configuration
type Config struct {
	URL           string
	ServiceRoleKey string
	BucketName    string
}

// Client wraps Supabase Storage for file operations
type Client struct {
	client *storage_go.Client
	bucket string
}

// NewClient creates a new storage client
func NewClient(config Config) (*Client, error) {
	if config.URL == "" || config.ServiceRoleKey == "" {
		return nil, fmt.Errorf("invalid storage configuration")
	}

	client := storage_go.NewClient(config.URL, config.ServiceRoleKey, nil)

	return &Client{
		client: client,
		bucket: config.BucketName,
	}, nil
}

// FileUploadOptions holds file upload options
type FileUploadOptions struct {
	FileName    string
	ContentType string
	UserID      string
	CallID      string
	IsPublic    bool
}

// UploadFile uploads a file to storage
func (c *Client) UploadFile(ctx context.Context, reader io.Reader, opts FileUploadOptions) (string, string, error) {
	// Generate unique file path
	fileID := uuid.New().String()
	extension := filepath.Ext(opts.FileName)
	storagePath := fmt.Sprintf("%s/%s/%s%s", opts.UserID, opts.CallID, fileID, extension)

	// Upload file
	_, err := c.client.UploadFile(c.bucket, storagePath, reader)
	if err != nil {
		return "", "", fmt.Errorf("failed to upload file: %w", err)
	}

	// Generate URL
	var url string
	if opts.IsPublic {
		publicURL := c.client.GetPublicUrl(c.bucket, storagePath)
		url = publicURL.SignedURL
	} else {
		// Generate signed URL valid for 1 hour
		signedURL, err := c.client.CreateSignedUrl(c.bucket, storagePath, 3600)
		if err != nil {
			return "", "", fmt.Errorf("failed to create signed URL: %w", err)
		}
		url = signedURL.SignedURL
	}

	return storagePath, url, nil
}

// GetSignedURL generates a temporary signed URL for a file
func (c *Client) GetSignedURL(ctx context.Context, path string, expiresIn int) (string, error) {
	result, err := c.client.CreateSignedUrl(c.bucket, path, expiresIn)
	if err != nil {
		return "", fmt.Errorf("failed to create signed URL: %w", err)
	}

	return result.SignedURL, nil
}

// DeleteFile deletes a file from storage
func (c *Client) DeleteFile(ctx context.Context, path string) error {
	_, err := c.client.RemoveFile(c.bucket, []string{path})
	if err != nil {
		return fmt.Errorf("failed to delete file: %w", err)
	}

	return nil
}

// ListFiles lists files in a directory
func (c *Client) ListFiles(ctx context.Context, prefix string) ([]storage_go.FileObject, error) {
	result, err := c.client.ListFiles(c.bucket, prefix, storage_go.FileSearchOptions{})
	if err != nil {
		return nil, fmt.Errorf("failed to list files: %w", err)
	}

	return result, nil
}

// GetFileInfo retrieves file metadata
func (c *Client) GetFileInfo(ctx context.Context, path string) (*storage_go.FileObject, error) {
	// List with specific path
	result, err := c.client.ListFiles(c.bucket, path, storage_go.FileSearchOptions{
		Limit: 1,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to get file info: %w", err)
	}

	if len(result) == 0 {
		return nil, fmt.Errorf("file not found")
	}

	return &result[0], nil
}

// MoveFile moves a file to a new location
func (c *Client) MoveFile(ctx context.Context, fromPath, toPath string) error {
	_, err := c.client.MoveFile(c.bucket, fromPath, toPath)
	if err != nil {
		return fmt.Errorf("failed to move file: %w", err)
	}

	return nil
}

// CopyFile copies a file to a new location
func (c *Client) CopyFile(ctx context.Context, fromPath, toPath string) error {
	// Note: Supabase storage-go doesn't have CopyFile, need to download and re-upload
	// For now, return not implemented error
	return fmt.Errorf("copy file not implemented")
}

// GeneratePresignedUploadURL generates a URL for direct upload
func (c *Client) GeneratePresignedUploadURL(ctx context.Context, path string, expiresIn time.Duration) (string, error) {
	// For direct uploads, we use signed URLs
	result, err := c.client.CreateSignedUploadUrl(c.bucket, path)
	if err != nil {
		return "", fmt.Errorf("failed to create upload URL: %w", err)
	}

	return result.Url, nil
}

// Close closes storage client connections
func (c *Client) Close() error {
	// No explicit close needed for storage client
	return nil
}
