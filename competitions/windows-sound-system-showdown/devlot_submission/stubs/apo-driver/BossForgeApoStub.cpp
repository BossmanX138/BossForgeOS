#include "BossForgeApoStub.h"

BossForgeEndpointApo::BossForgeEndpointApo() = default;
BossForgeEndpointApo::~BossForgeEndpointApo() = default;

STDMETHODIMP BossForgeEndpointApo::LockForProcess(
    UINT32 u32NumInputConnections,
    APO_CONNECTION_DESCRIPTOR** ppInputConnections,
    UINT32 u32NumOutputConnections,
    APO_CONNECTION_DESCRIPTOR** ppOutputConnections)
{
    UNREFERENCED_PARAMETER(u32NumInputConnections);
    UNREFERENCED_PARAMETER(ppInputConnections);
    UNREFERENCED_PARAMETER(u32NumOutputConnections);
    UNREFERENCED_PARAMETER(ppOutputConnections);

    // TODO: validate media types and allocate DSP state.
    return S_OK;
}

STDMETHODIMP_(void) BossForgeEndpointApo::APOProcess(
    UINT32 u32NumInputConnections,
    APO_CONNECTION_PROPERTY** ppInputConnections,
    UINT32 u32NumOutputConnections,
    APO_CONNECTION_PROPERTY** ppOutputConnections)
{
    UNREFERENCED_PARAMETER(u32NumInputConnections);
    UNREFERENCED_PARAMETER(u32NumOutputConnections);

    // TODO: apply 10-band EQ and stereo->7.2 mapping in endpoint pipeline.
    // Current stub performs pass-through for scaffolding.
    if (!ppInputConnections || !ppOutputConnections) {
        return;
    }

    auto* inConn = ppInputConnections[0];
    auto* outConn = ppOutputConnections[0];
    if (!inConn || !outConn || !inConn->pBuffer || !outConn->pBuffer) {
        return;
    }

    const auto bytesToCopy = min(inConn->u32BufferFlags == BUFFER_VALID ? inConn->u32ValidFrameCount : 0,
                                 outConn->u32ValidFrameCount);

    if (bytesToCopy == 0) {
        outConn->u32BufferFlags = BUFFER_SILENT;
        return;
    }

    // NOTE: Frame-size aware copy is required in full implementation.
    memcpy(outConn->pBuffer, inConn->pBuffer, bytesToCopy);
    outConn->u32BufferFlags = BUFFER_VALID;
}
