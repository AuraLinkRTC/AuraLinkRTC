"""
Generated gRPC client and server code for AIC Compression Protocol
Auto-generated from aic_compression.proto
"""

import grpc
from . import aic_compression_pb2 as aic__compression__pb2


class AICCompressionServiceStub:
    """Client for AICCompressionService"""

    def __init__(self, channel):
        self.CompressFrame = channel.unary_unary(
            '/auralink.aic.v1.AICCompressionService/CompressFrame',
            request_serializer=aic__compression__pb2.CompressFrameRequest.SerializeToString,
            response_deserializer=aic__compression__pb2.CompressFrameResponse.FromString,
        )
        self.CompressStream = channel.stream_stream(
            '/auralink.aic.v1.AICCompressionService/CompressStream',
            request_serializer=aic__compression__pb2.CompressFrameRequest.SerializeToString,
            response_deserializer=aic__compression__pb2.CompressFrameResponse.FromString,
        )
        self.GetCompressionHints = channel.unary_unary(
            '/auralink.aic.v1.AICCompressionService/GetCompressionHints',
            request_serializer=aic__compression__pb2.CompressionHintRequest.SerializeToString,
            response_deserializer=aic__compression__pb2.CompressionHintResponse.FromString,
        )
        self.AnalyzeNetworkConditions = channel.unary_unary(
            '/auralink.aic.v1.AICCompressionService/AnalyzeNetworkConditions',
            request_serializer=aic__compression__pb2.NetworkAnalysisRequest.SerializeToString,
            response_deserializer=aic__compression__pb2.NetworkAnalysisResponse.FromString,
        )
        self.HealthCheck = channel.unary_unary(
            '/auralink.aic.v1.AICCompressionService/HealthCheck',
            request_serializer=aic__compression__pb2.HealthCheckRequest.SerializeToString,
            response_deserializer=aic__compression__pb2.HealthCheckResponse.FromString,
        )


class AICCompressionServiceServicer:
    """Server interface for AICCompressionService"""

    def CompressFrame(self, request, context):
        """Compress a single frame with AI"""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def CompressStream(self, request_iterator, context):
        """Compress frames in streaming mode (real-time)"""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def GetCompressionHints(self, request, context):
        """Get compression hints without actual compression (prediction)"""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def AnalyzeNetworkConditions(self, request, context):
        """Analyze network conditions for adaptive compression"""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def HealthCheck(self, request, context):
        """Health check for AIC service"""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_AICCompressionServiceServicer_to_server(servicer, server):
    """Register servicer with server"""
    rpc_method_handlers = {
        'CompressFrame': grpc.unary_unary_rpc_method_handler(
            servicer.CompressFrame,
            request_deserializer=aic__compression__pb2.CompressFrameRequest.FromString,
            response_serializer=aic__compression__pb2.CompressFrameResponse.SerializeToString,
        ),
        'CompressStream': grpc.stream_stream_rpc_method_handler(
            servicer.CompressStream,
            request_deserializer=aic__compression__pb2.CompressFrameRequest.FromString,
            response_serializer=aic__compression__pb2.CompressFrameResponse.SerializeToString,
        ),
        'GetCompressionHints': grpc.unary_unary_rpc_method_handler(
            servicer.GetCompressionHints,
            request_deserializer=aic__compression__pb2.CompressionHintRequest.FromString,
            response_serializer=aic__compression__pb2.CompressionHintResponse.SerializeToString,
        ),
        'AnalyzeNetworkConditions': grpc.unary_unary_rpc_method_handler(
            servicer.AnalyzeNetworkConditions,
            request_deserializer=aic__compression__pb2.NetworkAnalysisRequest.FromString,
            response_serializer=aic__compression__pb2.NetworkAnalysisResponse.SerializeToString,
        ),
        'HealthCheck': grpc.unary_unary_rpc_method_handler(
            servicer.HealthCheck,
            request_deserializer=aic__compression__pb2.HealthCheckRequest.FromString,
            response_serializer=aic__compression__pb2.HealthCheckResponse.SerializeToString,
        ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
        'auralink.aic.v1.AICCompressionService',
        rpc_method_handlers
    )
    server.add_generic_rpc_handlers((generic_handler,))
