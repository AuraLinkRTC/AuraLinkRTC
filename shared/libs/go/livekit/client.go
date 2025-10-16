package livekit

import (
	"context"
	"fmt"
	"time"

	"github.com/livekit/protocol/auth"
	"github.com/livekit/protocol/livekit"
	lksdk "github.com/livekit/server-sdk-go/v2"
)

// Config holds LiveKit client configuration
type Config struct {
	URL       string
	APIKey    string
	APISecret string
}

// Client wraps LiveKit SDK for room management
type Client struct {
	roomClient *lksdk.RoomServiceClient
	config     Config
}

// NewClient creates a new LiveKit client
func NewClient(config Config) (*Client, error) {
	if config.URL == "" || config.APIKey == "" || config.APISecret == "" {
		return nil, fmt.Errorf("invalid LiveKit configuration")
	}

	roomClient := lksdk.NewRoomServiceClient(config.URL, config.APIKey, config.APISecret)

	return &Client{
		roomClient: roomClient,
		config:     config,
	}, nil
}

// RoomOptions holds room creation options
type RoomOptions struct {
	Name            string
	EmptyTimeout    uint32
	MaxParticipants uint32
	Metadata        string
}

// CreateRoom creates a new LiveKit room
func (c *Client) CreateRoom(ctx context.Context, opts RoomOptions) (*livekit.Room, error) {
	room, err := c.roomClient.CreateRoom(ctx, &livekit.CreateRoomRequest{
		Name:            opts.Name,
		EmptyTimeout:    opts.EmptyTimeout,
		MaxParticipants: opts.MaxParticipants,
		Metadata:        opts.Metadata,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to create room: %w", err)
	}

	return room, nil
}

// GetRoom retrieves room information
func (c *Client) GetRoom(ctx context.Context, roomName string) (*livekit.Room, error) {
	rooms, err := c.roomClient.ListRooms(ctx, &livekit.ListRoomsRequest{
		Names: []string{roomName},
	})
	if err != nil {
		return nil, fmt.Errorf("failed to get room: %w", err)
	}

	if len(rooms.Rooms) == 0 {
		return nil, fmt.Errorf("room not found")
	}

	return rooms.Rooms[0], nil
}

// DeleteRoom deletes a LiveKit room
func (c *Client) DeleteRoom(ctx context.Context, roomName string) error {
	_, err := c.roomClient.DeleteRoom(ctx, &livekit.DeleteRoomRequest{
		Room: roomName,
	})
	if err != nil {
		return fmt.Errorf("failed to delete room: %w", err)
	}

	return nil
}

// ListRooms lists all active rooms
func (c *Client) ListRooms(ctx context.Context) ([]*livekit.Room, error) {
	result, err := c.roomClient.ListRooms(ctx, &livekit.ListRoomsRequest{})
	if err != nil {
		return nil, fmt.Errorf("failed to list rooms: %w", err)
	}

	return result.Rooms, nil
}

// GetParticipants lists participants in a room
func (c *Client) GetParticipants(ctx context.Context, roomName string) ([]*livekit.ParticipantInfo, error) {
	result, err := c.roomClient.ListParticipants(ctx, &livekit.ListParticipantsRequest{
		Room: roomName,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to list participants: %w", err)
	}

	return result.Participants, nil
}

// RemoveParticipant removes a participant from a room
func (c *Client) RemoveParticipant(ctx context.Context, roomName, identity string) error {
	_, err := c.roomClient.RemoveParticipant(ctx, &livekit.RoomParticipantIdentity{
		Room:     roomName,
		Identity: identity,
	})
	if err != nil {
		return fmt.Errorf("failed to remove participant: %w", err)
	}

	return nil
}

// TokenOptions holds token generation options
type TokenOptions struct {
	Identity   string
	RoomName   string
	Name       string
	Metadata   string
	CanPublish bool
	CanSubscribe bool
	CanPublishData bool
	ValidFor   time.Duration
}

// GenerateAccessToken generates a JWT token for room access
func (c *Client) GenerateAccessToken(opts TokenOptions) (string, error) {
	at := auth.NewAccessToken(c.config.APIKey, c.config.APISecret)
	
	grant := &auth.VideoGrant{
		RoomJoin:       true,
		Room:           opts.RoomName,
		CanPublish:     &opts.CanPublish,
		CanSubscribe:   &opts.CanSubscribe,
		CanPublishData: &opts.CanPublishData,
	}

	at.AddGrant(grant).
		SetIdentity(opts.Identity).
		SetName(opts.Name).
		SetMetadata(opts.Metadata).
		SetValidFor(opts.ValidFor)

	token, err := at.ToJWT()
	if err != nil {
		return "", fmt.Errorf("failed to generate token: %w", err)
	}

	return token, nil
}

// UpdateRoomMetadata updates room metadata
func (c *Client) UpdateRoomMetadata(ctx context.Context, roomName, metadata string) (*livekit.Room, error) {
	room, err := c.roomClient.UpdateRoomMetadata(ctx, &livekit.UpdateRoomMetadataRequest{
		Room:     roomName,
		Metadata: metadata,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to update room metadata: %w", err)
	}

	return room, nil
}

// UpdateParticipantMetadata updates participant metadata
func (c *Client) UpdateParticipantMetadata(ctx context.Context, roomName, identity, metadata string) (*livekit.ParticipantInfo, error) {
	participant, err := c.roomClient.UpdateParticipant(ctx, &livekit.UpdateParticipantRequest{
		Room:     roomName,
		Identity: identity,
		Metadata: metadata,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to update participant: %w", err)
	}

	return participant, nil
}

// MutePublishedTrack mutes a participant's track
func (c *Client) MutePublishedTrack(ctx context.Context, roomName, identity, trackSid string, muted bool) (*livekit.MuteRoomTrackResponse, error) {
	response, err := c.roomClient.MutePublishedTrack(ctx, &livekit.MuteRoomTrackRequest{
		Room:     roomName,
		Identity: identity,
		TrackSid: trackSid,
		Muted:    muted,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to mute track: %w", err)
	}

	return response, nil
}

// SendData sends data to participants in a room
func (c *Client) SendData(ctx context.Context, roomName string, data []byte, kind livekit.DataPacket_Kind, destinationIdentities []string) error {
	_, err := c.roomClient.SendData(ctx, &livekit.SendDataRequest{
		Room:                   roomName,
		Data:                   data,
		Kind:                   kind,
		DestinationIdentities:  destinationIdentities,
	})
	if err != nil {
		return fmt.Errorf("failed to send data: %w", err)
	}

	return nil
}

// Close closes the LiveKit client connection
func (c *Client) Close() error {
	// SDK doesn't have explicit close, but we could add cleanup here if needed
	return nil
}
