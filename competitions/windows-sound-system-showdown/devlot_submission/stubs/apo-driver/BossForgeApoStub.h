#pragma once

#include <audioenginebaseapo.h>
#include <wrl.h>

// Stub COM class for an endpoint effect APO.
class BossForgeEndpointApo : public CBaseAudioProcessingObject
{
public:
    BossForgeEndpointApo();
    ~BossForgeEndpointApo() override;

    // Called by the Windows audio engine for frame processing.
    STDMETHOD_(void, APOProcess)(
        UINT32 u32NumInputConnections,
        APO_CONNECTION_PROPERTY** ppInputConnections,
        UINT32 u32NumOutputConnections,
        APO_CONNECTION_PROPERTY** ppOutputConnections) override;

    STDMETHOD(LockForProcess)(
        UINT32 u32NumInputConnections,
        APO_CONNECTION_DESCRIPTOR** ppInputConnections,
        UINT32 u32NumOutputConnections,
        APO_CONNECTION_DESCRIPTOR** ppOutputConnections) override;
};
