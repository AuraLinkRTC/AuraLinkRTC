package tracing

import (
	"context"
	"fmt"
	"io"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/jaeger"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.17.0"
	"go.opentelemetry.io/otel/trace"
)

// TracerConfig holds tracer configuration
type TracerConfig struct {
	ServiceName    string
	ServiceVersion string
	Environment    string
	JaegerEndpoint string
	SamplingRate   float64
	Enabled        bool
}

// DefaultTracerConfig returns default tracer configuration
func DefaultTracerConfig(serviceName string) TracerConfig {
	return TracerConfig{
		ServiceName:    serviceName,
		ServiceVersion: "1.0.0",
		Environment:    "development",
		JaegerEndpoint: "http://localhost:14268/api/traces",
		SamplingRate:   0.1, // Sample 10% of traces
		Enabled:        true,
	}
}

// TracerProvider wraps the OpenTelemetry tracer provider
type TracerProvider struct {
	provider *sdktrace.TracerProvider
	config   TracerConfig
}

// InitTracer initializes the Jaeger tracer
func InitTracer(config TracerConfig) (*TracerProvider, error) {
	if !config.Enabled {
		return &TracerProvider{config: config}, nil
	}

	// Create Jaeger exporter
	exporter, err := jaeger.New(jaeger.WithCollectorEndpoint(jaeger.WithEndpoint(config.JaegerEndpoint)))
	if err != nil {
		return nil, fmt.Errorf("failed to create Jaeger exporter: %w", err)
	}

	// Create resource with service information
	res, err := resource.Merge(
		resource.Default(),
		resource.NewWithAttributes(
			semconv.SchemaURL,
			semconv.ServiceName(config.ServiceName),
			semconv.ServiceVersion(config.ServiceVersion),
			semconv.DeploymentEnvironment(config.Environment),
		),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create resource: %w", err)
	}

	// Create trace provider with sampling
	var sampler sdktrace.Sampler
	if config.SamplingRate >= 1.0 {
		sampler = sdktrace.AlwaysSample()
	} else if config.SamplingRate <= 0 {
		sampler = sdktrace.NeverSample()
	} else {
		sampler = sdktrace.TraceIDRatioBased(config.SamplingRate)
	}

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(res),
		sdktrace.WithSampler(sampler),
	)

	// Set global tracer provider
	otel.SetTracerProvider(tp)

	// Set global propagator for context propagation
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))

	return &TracerProvider{
		provider: tp,
		config:   config,
	}, nil
}

// Tracer returns a tracer for the given component
func (tp *TracerProvider) Tracer(componentName string) trace.Tracer {
	if tp.provider == nil {
		return otel.Tracer(componentName)
	}
	return tp.provider.Tracer(componentName)
}

// Shutdown shuts down the tracer provider
func (tp *TracerProvider) Shutdown(ctx context.Context) error {
	if tp.provider == nil {
		return nil
	}
	return tp.provider.Shutdown(ctx)
}

// StartSpan starts a new span with the given name
func StartSpan(ctx context.Context, tracer trace.Tracer, spanName string, opts ...trace.SpanStartOption) (context.Context, trace.Span) {
	return tracer.Start(ctx, spanName, opts...)
}

// StartSpanWithAttributes starts a new span with attributes
func StartSpanWithAttributes(ctx context.Context, tracer trace.Tracer, spanName string, attrs map[string]string) (context.Context, trace.Span) {
	spanAttrs := make([]attribute.KeyValue, 0, len(attrs))
	for k, v := range attrs {
		spanAttrs = append(spanAttrs, attribute.String(k, v))
	}
	
	return tracer.Start(ctx, spanName, trace.WithAttributes(spanAttrs...))
}

// AddSpanAttributes adds attributes to the current span
func AddSpanAttributes(span trace.Span, attrs map[string]string) {
	for k, v := range attrs {
		span.SetAttributes(attribute.String(k, v))
	}
}

// AddSpanError adds an error to the current span
func AddSpanError(span trace.Span, err error) {
	if err != nil {
		span.RecordError(err)
		span.SetAttributes(attribute.Bool("error", true))
	}
}

// AddSpanEvent adds an event to the current span
func AddSpanEvent(span trace.Span, name string, attrs ...attribute.KeyValue) {
	span.AddEvent(name, trace.WithAttributes(attrs...))
}

// SpanFromContext returns the current span from context
func SpanFromContext(ctx context.Context) trace.Span {
	return trace.SpanFromContext(ctx)
}

// ContextWithSpan returns a context with the span
func ContextWithSpan(ctx context.Context, span trace.Span) context.Context {
	return trace.ContextWithSpan(ctx, span)
}

// TraceID returns the trace ID from the span
func TraceID(span trace.Span) string {
	return span.SpanContext().TraceID().String()
}

// SpanID returns the span ID from the span
func SpanID(span trace.Span) string {
	return span.SpanContext().SpanID().String()
}

// InjectTraceContext injects trace context into a carrier
func InjectTraceContext(ctx context.Context, carrier propagation.TextMapCarrier) {
	otel.GetTextMapPropagator().Inject(ctx, carrier)
}

// ExtractTraceContext extracts trace context from a carrier
func ExtractTraceContext(ctx context.Context, carrier propagation.TextMapCarrier) context.Context {
	return otel.GetTextMapPropagator().Extract(ctx, carrier)
}

// TracedOperation wraps an operation with tracing
func TracedOperation(ctx context.Context, tracer trace.Tracer, operationName string, fn func(context.Context) error) error {
	ctx, span := tracer.Start(ctx, operationName)
	defer span.End()

	err := fn(ctx)
	if err != nil {
		AddSpanError(span, err)
	}

	return err
}

// TracedOperationWithResult wraps an operation with tracing and returns a result
func TracedOperationWithResult[T any](ctx context.Context, tracer trace.Tracer, operationName string, fn func(context.Context) (T, error)) (T, error) {
	ctx, span := tracer.Start(ctx, operationName)
	defer span.End()

	result, err := fn(ctx)
	if err != nil {
		AddSpanError(span, err)
	}

	return result, err
}

// NoOpTracer returns a no-op tracer
func NoOpTracer() trace.Tracer {
	return otel.Tracer("noop")
}
